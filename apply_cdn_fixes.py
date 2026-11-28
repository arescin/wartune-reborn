import os, sys, struct, zlib, re, shutil

def generate_symbol_aliases(sym_name):
    m = re.match(r'^(asset\.[^.]+)\.([^.]+)$', sym_name)
    if not m:
        return []

    prefix = m.group(1)
    suffix = m.group(2)
    aliases_prefix = set()

    m_job_sex = re.match(r'^(.*?)(up|down)?_(\d+)_(\d+)$', prefix)
    if m_job_sex:
        base = m_job_sex.group(1)
        dir_mod = m_job_sex.group(2) or ''
        job = m_job_sex.group(3)
        sex = m_job_sex.group(4)
        aliases_prefix.add(f"{base}_{job}")
        aliases_prefix.add(f"{base}_{sex}")
        aliases_prefix.add(f"{base}_1")
        aliases_prefix.add(f"{base}_2")
        if dir_mod:
            aliases_prefix.add(f"{base}{dir_mod}_{job}")
            aliases_prefix.add(f"{base}{dir_mod}_{sex}")
            aliases_prefix.add(f"{base}_{job}_{sex}")
            aliases_prefix.add(f"{base}_{job}")
            aliases_prefix.add(f"{base}_{sex}")
    else:
        m_single = re.match(r'^(.*?)(up|down)?_(\d+)$', prefix)
        if m_single:
            base = m_single.group(1)
            dir_mod = m_single.group(2) or ''
            num = m_single.group(3)
            aliases_prefix.add(f"{base}_{num}_1")
            aliases_prefix.add(f"{base}_{num}_0")
            aliases_prefix.add(f"{base}_2_1")
            aliases_prefix.add(f"{base}_1_1")
            aliases_prefix.add(f"{base}_2")
            aliases_prefix.add(f"{base}_1")
            if dir_mod:
                aliases_prefix.add(f"{base}{dir_mod}_{num}_1")
                aliases_prefix.add(f"{base}{dir_mod}_{num}_0")
                aliases_prefix.add(f"{base}_{num}")

    return [f"{p}.{suffix}" for p in aliases_prefix if f"{p}.{suffix}" != sym_name]

def patch_swf_data(swf_data):
    is_cws = swf_data[:3] == b'CWS'
    is_fws = swf_data[:3] == b'FWS'
    if not (is_cws or is_fws):
        return swf_data

    if is_cws:
        decomp = swf_data[:8] + zlib.decompress(swf_data[8:])
    else:
        decomp = swf_data

    pos = 8
    nbits = decomp[pos] >> 3
    pos += (5 + nbits * 4 + 7) // 8 + 4

    new_tags = bytearray(decomp[:pos])
    modified = False

    while pos < len(decomp):
        tag_start = pos
        tag_header = struct.unpack('<H', decomp[pos:pos+2])[0]
        pos += 2
        tag_type = tag_header >> 6
        tag_len = tag_header & 0x3F
        has_long_len = (tag_len == 0x3F)
        if has_long_len:
            tag_len = struct.unpack('<I', decomp[pos:pos+4])[0]
            pos += 4
        tag_data = decomp[pos:pos+tag_len]
        pos += tag_len

        if tag_type == 76: # SymbolClass
            num_symbols = struct.unpack('<H', tag_data[:2])[0]
            spos = 2
            symbols = []
            for _ in range(num_symbols):
                sym_id = struct.unpack('<H', tag_data[spos:spos+2])[0]
                spos += 2
                null_pos = tag_data.find(b'\x00', spos)
                sym_name = tag_data[spos:null_pos].decode('utf-8', errors='replace')
                spos = null_pos + 1
                symbols.append((sym_id, sym_name))

            new_symbols = list(symbols)
            existing_names = set(s[1] for s in symbols)

            for sym_id, sym_name in symbols:
                for alias in generate_symbol_aliases(sym_name):
                    if alias not in existing_names:
                        new_symbols.append((sym_id, alias))
                        existing_names.add(alias)

            if len(new_symbols) > len(symbols):
                modified = True
                payload = bytearray()
                payload.extend(struct.pack('<H', len(new_symbols)))
                for sid, sname in new_symbols:
                    payload.extend(struct.pack('<H', sid))
                    payload.extend(sname.encode('utf-8') + b'\x00')

                if len(payload) >= 63:
                    new_tags.extend(struct.pack('<H', (76 << 6) | 0x3F))
                    new_tags.extend(struct.pack('<I', len(payload)))
                else:
                    new_tags.extend(struct.pack('<H', (76 << 6) | len(payload)))
                new_tags.extend(payload)
                continue

        new_tags.extend(decomp[tag_start:pos])
        if tag_type == 0:
            break

    if not modified:
        return swf_data

    new_decomp_len = len(new_tags)
    new_tags[4:8] = struct.pack('<I', new_decomp_len)

    if is_cws:
        return new_tags[:8] + zlib.compress(new_tags[8:])
    else:
        return bytes(new_tags)

def patch_file(fpath):
    if os.path.islink(fpath):
        return False
    try:
        with open(fpath, 'rb') as f:
            data = f.read()
    except Exception:
        return False

    pos_cws = data.find(b'CWS')
    pos_fws = data.find(b'FWS')
    pos_swf = min(pos_cws, pos_fws) if pos_cws != -1 and pos_fws != -1 else max(pos_cws, pos_fws)
    if pos_swf == -1:
        return False

    bswf_header = data[:pos_swf]
    swf_payload = data[pos_swf:]

    try:
        patched = patch_swf_data(swf_payload)
    except Exception:
        return False

    if patched != swf_payload:
        with open(fpath, 'wb') as f:
            f.write(bswf_header + patched)
        return True
    return False

def clean_spurious_swf_links(avatar_dir):
    # Remove symlinks .swf -> .bswf que quebram o Loader.load() do Flash
    for root, dirs, files in os.walk(avatar_dir):
        for f in files:
            if f.endswith('.swf'):
                p = os.path.join(root, f)
                if os.path.islink(p):
                    target = os.readlink(p)
                    if 'bswf' in target:
                        os.unlink(p)

def process_avatar_directory(avatar_dir):
    print("Iniciando varredura em:", avatar_dir)
    patched_count = 0
    created_count = 0

    clean_spurious_swf_links(avatar_dir)

    for entry in os.scandir(avatar_dir):
        if not entry.is_dir():
            continue
        folder = entry.path

        # 1. Patch todos os .bswf reais
        for fname in os.listdir(folder):
            if fname.endswith('.bswf'):
                fpath = os.path.join(folder, fname)
                if patch_file(fpath):
                    patched_count += 1

        # 2. Assegurar cópias/symlinks recíprocos de 2 <-> 2_1 e 1 <-> 1_1
        files = set(os.listdir(folder))
        pairs = [
            ('2_1.bswf', '2.bswf'),
            ('2.bswf', '2_1.bswf'),
            ('1_1.bswf', '1.bswf'),
            ('1.bswf', '1_1.bswf'),
            ('2_0.bswf', '0.bswf'),
            ('1_0.bswf', '0.bswf'),
        ]
        for src, dst in pairs:
            src_path = os.path.join(folder, src)
            dst_path = os.path.join(folder, dst)
            if src in files and dst not in files:
                try:
                    os.symlink(src, dst_path)
                    files.add(dst)
                    created_count += 1
                except Exception:
                    pass

    print(f"Varredura concluída: {patched_count} arquivos bswf patchados, {created_count} links de compatibilidade criados.")

def process_equip_show_directory(equip_show_dir):
    print("Processando equip_show:", equip_show_dir)
    created = 0
    for root, dirs, files in os.walk(equip_show_dir):
        fset = set(files)
        # Se tem 2_1.swf e falta 1.swf ou 2.swf
        if '2_1.swf' in fset:
            for want in ['1.swf', '2.swf']:
                if want not in fset:
                    dst = os.path.join(root, want)
                    try:
                        os.symlink('2_1.swf', dst)
                        fset.add(want)
                        created += 1
                    except Exception:
                        pass
        # Se tem 1.swf e falta 2_1.swf ou 2.swf
        if '1.swf' in fset:
            for want in ['2_1.swf', '2.swf']:
                if want not in fset:
                    dst = os.path.join(root, want)
                    try:
                        os.symlink('1.swf', dst)
                        fset.add(want)
                        created += 1
                    except Exception:
                        pass
        # Se tem 0.swf e falta 2_0.swf
        if '0.swf' in fset and '2_0.swf' not in fset:
            dst = os.path.join(root, '2_0.swf')
            try:
                os.symlink('0.swf', dst)
                fset.add('2_0.swf')
                created += 1
            except Exception:
                pass
        # Se tem 2_0.swf e falta 0.swf
        if '2_0.swf' in fset and '0.swf' not in fset:
            dst = os.path.join(root, '0.swf')
            try:
                os.symlink('2_0.swf', dst)
                fset.add('0.swf')
                created += 1
            except Exception:
                pass

    print(f"equip_show concluído: {created} links criados.")

if __name__ == '__main__':
    avatar_dir = '/opt/wartune-cdn/res134-bmclas-sq.7road.net/swf/avatar'
    equip_show_dir = '/opt/wartune-cdn/res134-bmclas-sq.7road.net/equip_show'
    if os.path.exists(avatar_dir):
        process_avatar_directory(avatar_dir)
    if os.path.exists(equip_show_dir):
        process_equip_show_directory(equip_show_dir)
