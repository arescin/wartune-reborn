import xml.etree.ElementTree as ET

tree = ET.parse('G:/projects/legend-online-main/raw/xml/tempinfos/PawnTempInfos.xml')
root = tree.getroot()

for p in root.findall('PawnTempInfo'):
    tid = p.get('TemplateId')
    swf = p.get('Swf', '')
    if 'monster002' in swf.lower() or tid in ('1001', '2001', '2002', '2003', '2006'):
        print(f"TemplateId={tid}, Swf='{swf}', Name='{p.get('PawnName')}'")
