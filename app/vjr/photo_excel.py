"""Insert report photos into the original L10:U27 regions, preserving OOXML."""
from io import BytesIO
import math
import re
from PIL import Image
from openpyxl.utils import get_column_letter
from .photo_storage import PhotoError, PhotoStorage, SLOTS, validate_photo_state

EMU = 9525
ANCHOR = re.compile(r'<xdr:(oneCellAnchor|twoCellAnchor)\b.*?</xdr:\1>',re.S)
DRAW_NS = 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
ART_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def column_pixels(sheet, index):
    width = sheet.sheet_format.defaultColWidth or 8.43
    for dimension in sheet.column_dimensions.values():
        if dimension.min and dimension.min<=index<=(dimension.max or dimension.min):
            width = 0 if dimension.hidden else dimension.width
            break
    return int(width*7+5) if width>=1 else int(width*12+.5)


def region_dimensions(sheet):
    widths = [column_pixels(sheet,index) for index in range(12,22)]
    heights = [int(math.ceil((sheet.row_dimensions[index].height or sheet.sheet_format.defaultRowHeight or 15)*96/72))
               for index in range(10,28)]
    return widths,heights


def offset_position(start, sizes, offset):
    index = start
    for size in sizes:
        if offset<size:
            break
        offset -= size; index += 1
    return index,int(round(offset*EMU))


def image_anchor(sheet, image_size, relationship, picture_id, name):
    widths,heights = region_dimensions(sheet)
    available_width,available_height = sum(widths),sum(heights)
    scale = min(1.0,available_width/image_size[0],available_height/image_size[1])
    width,height = image_size[0]*scale,image_size[1]*scale
    column,x_offset = offset_position(11,widths,(available_width-width)/2)
    row,y_offset = offset_position(9,heights,(available_height-height)/2)
    cx,cy = int(round(width*EMU)),int(round(height*EMU))
    return ('<xdr:oneCellAnchor xmlns:xdr="%s" xmlns:a="%s" xmlns:r="%s">'
        '<xdr:from><xdr:col>%s</xdr:col><xdr:colOff>%s</xdr:colOff><xdr:row>%s</xdr:row><xdr:rowOff>%s</xdr:rowOff></xdr:from>'
        '<xdr:ext cx="%s" cy="%s"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="%s" name="%s"/>'
        '<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>'
        '<xdr:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
        '<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%s" cy="%s"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>') % (
        DRAW_NS,ART_NS,REL_NS,column,x_offset,row,y_offset,cx,cy,picture_id,name,relationship,cx,cy)


def photo_parts(source, workbook, report, root):
    photos = report.get('photos',{})
    if not photos:
        return {}
    validate_photo_state(report)
    if root is None:
        raise PhotoError('Photo storage location is required to export this VJR.')
    storage = PhotoStorage(root)
    parts = {}
    for slot,number,sheet_name in ((SLOTS[0],6,'4. Departure Report'),(SLOTS[1],7,'5. Arrival Report')):
        reference = photos.get(slot)
        if not reference:
            continue
        path = storage.image_path(reference)
        try:
            with Image.open(path) as image:
                image.load(); size = image.size
                widths,heights = region_dimensions(workbook[sheet_name])
                image.thumbnail((min(1800,sum(widths)*2),min(1800,sum(heights)*2)),Image.Resampling.LANCZOS)
                size = image.size
                payload = BytesIO(); image.convert('RGB').save(payload,'JPEG',quality=90,optimize=True)
        except OSError as error:
            raise PhotoError('Stored photo cannot be decoded. Replace it via QR before exporting.') from error
        # Anchor uses the oriented display size so small photographs are never enlarged.
        drawing_name = 'xl/drawings/drawing%s.xml' % number
        relationships_name = 'xl/drawings/_rels/drawing%s.xml.rels' % number
        drawing = source.read(drawing_name).decode('utf-8')
        def keep_unrelated(match):
            anchor = match.group(0)
            col = re.search(r'<xdr:col>(\d+)</xdr:col>',anchor)
            row = re.search(r'<xdr:row>(\d+)</xdr:row>',anchor)
            photo = '<xdr:pic>' in anchor and col and row and 11<=int(col[1])<=20 and 9<=int(row[1])<=26
            return '' if photo else anchor
        drawing = ANCHOR.sub(keep_unrelated,drawing)
        picture_id = max([int(value) for value in re.findall(r'<xdr:cNvPr\b[^>]*\bid="(\d+)"',drawing)]+[0])+1
        relationship = 'rIdVjrMobilePhoto'
        name = 'VJR '+('Departure' if number==6 else 'Arrival')+' Back Deck Photo'
        anchor = image_anchor(workbook[sheet_name],size,relationship,picture_id,name)
        drawing = drawing.replace('</xdr:wsDr>',anchor+'</xdr:wsDr>')
        parts[drawing_name] = drawing.encode('utf-8')
        media_name = 'vjr_mobile_%s.jpg' % ('departure' if number==6 else 'arrival')
        relationships = source.read(relationships_name).decode('utf-8')
        addition = '<Relationship Id="%s" Type="%s/image" Target="../media/%s"/>' % (relationship,REL_NS,media_name)
        parts[relationships_name] = relationships.replace('</Relationships>',addition+'</Relationships>').encode('utf-8')
        parts['xl/media/'+media_name] = payload.getvalue()
    types = source.read('[Content_Types].xml').decode('utf-8')
    if not re.search(r'<Default\b[^>]*\bExtension="jpg"',types):
        types = types.replace('</Types>','<Default Extension="jpg" ContentType="image/jpeg"/></Types>')
        parts['[Content_Types].xml'] = types.encode('utf-8')
    return parts
