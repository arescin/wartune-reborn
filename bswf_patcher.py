import struct, zlib

def patch_swf_symbols(swf_data, aliases_fn):
    is_cws = swf_data[:3] == b'CWS'
    if is_cws:
        decomp = swf_data[:8] + zlib.decompress(swf_data[8:])
    else:
        decomp = swf_data

    # Ler header do SWF
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
                extra_names = aliases_fn(sym_name)
                for en in extra_names:
                    if en not in existing_names:
                        new_symbols.append((sym_id, en))
                        existing_names.add(en)

            if len(new_symbols) > len(symbols):
                modified = True
                # reconstruir tag 76
                payload = bytearray()
                payload.extend(struct.pack('<H', len(new_symbols)))
                for sid, sname in new_symbols:
                    payload.extend(struct.pack('<H', sid))
                    payload.extend(sname.encode('utf-8') + b'\x00')

                # escrever tag header
                if len(payload) >= 63:
                    new_tags.extend(struct.pack('<H', (76 << 6) | 0x3F))
                    new_tags.extend(struct.pack('<I', len(payload)))
                else:
                    new_tags.extend(struct.pack('<H', (76 << 6) | len(payload)))
                new_tags.extend(payload)
                continue

        # tag inalterada
        new_tags.extend(decomp[tag_start:pos])
        if tag_type == 0:
            break

    if not modified:
        return swf_data

    # atualizar tamanho total no header descompactado (bytes 4..8)
    new_decomp_len = len(new_tags)
    new_tags[4:8] = struct.pack('<I', new_decomp_len)

    if is_cws:
        return new_tags[:8] + zlib.compress(new_tags[8:])
    else:
        return bytes(new_tags)

def patch_bswf_file(fpath, aliases_fn):
    with open(fpath, 'rb') as f:
        data = f.read()

    pos_cws = data.find(b'CWS')
    pos_fws = data.find(b'FWS')
    pos_swf = min(pos_cws, pos_fws) if pos_cws != -1 and pos_fws != -1 else max(pos_cws, pos_fws)
    if pos_swf == -1:
        return False

    bswf_header = data[:pos_swf]
    swf_payload = data[pos_swf:]

    patched_swf = patch_swf_symbols(swf_payload, aliases_fn)
    if patched_swf == swf_payload:
        return False

    with open(fpath, 'wb') as f:
        f.write(bswf_header + patched_swf)
    return True
