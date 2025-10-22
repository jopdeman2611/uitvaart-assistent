import os, zipfile, tempfile, shutil
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.dml import MSO_FILL
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.util import Emu
from PIL import Image


def verzamel_fotobestanden(uploadmap):
    fotopaden = []
    for root, _, files in os.walk(uploadmap):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                fotopaden.append(os.path.join(root, f))
    return fotopaden


def _compute_contain_size(img_w, img_h, box_w, box_h):
    r = min(box_w / img_w, box_h / img_h)
    return int(img_w * r), int(img_h * r)


def _crop_to_ratio(img, target_w, target_h):
    img_w, img_h = img.size
    target_ratio = target_w / target_h
    img_ratio = img_w / img_h
    if img_ratio > target_ratio:
        new_w = int(target_ratio * img_h)
        x0 = (img_w - new_w) // 2
        return img.crop((x0, 0, x0 + new_w, img_h))
    else:
        new_h = int(img_w / target_ratio)
        y0 = (img_h - new_h) // 2
        return img.crop((0, y0, img_w, y0 + new_h))


def _iter_replacement_targets(shapes):
    for sh in shapes:
        st = sh.shape_type

        if st == MSO_SHAPE_TYPE.GROUP:
            for inner in _iter_replacement_targets(sh.shapes):
                yield inner
            continue

        if getattr(sh, "is_placeholder", False):
            try:
                if sh.placeholder_format.type == PP_PLACEHOLDER.PICTURE:
                    yield ("placeholder", sh)
                    continue
            except Exception:
                pass

        if st == MSO_SHAPE_TYPE.PICTURE:
            yield ("picture", sh)
            continue

        try:
            if sh.fill.type == MSO_FILL.PICTURE:
                yield ("fill", sh)
                continue
        except Exception:
            pass


def vervang_alle_fotos(prs, fotopaden, ratio_mode="cover"):
    fotos = [f for f in fotopaden if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not fotos:
        print("Waarschuwing: geen foto's gevonden om te vervangen.")
        return 0

    foto_idx = 0
    vervangen = 0

    for s_idx, slide in enumerate(prs.slides, start=1):
        for kind, shape in _iter_replacement_targets(slide.shapes):
            if foto_idx >= len(fotos):
                continue

            path = fotos[foto_idx]

            try:
                if kind == "placeholder":
                    shape.insert_picture(path)
                    vervangen += 1

                elif kind == "picture":
                    left, top, width, height = shape.left, shape.top, shape.width, shape.height

                    if ratio_mode == "fit":
                        with Image.open(path) as im:
                            new_w_px, new_h_px = _compute_contain_size(im.width, im.height, width, height)
                        new_left = left + Emu((width - new_w_px) // 2)
                        new_top = top + Emu((height - new_h_px) // 2)
                        shape._element.getparent().remove(shape._element)
                        slide.shapes.add_picture(path, new_left, new_top, width=Emu(new_w_px), height=Emu(new_h_px))
                    else:
                        with Image.open(path) as im:
                            cropped = _crop_to_ratio(im, width, height)
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                                cropped.save(tf.name)
                                tmp = tf.name
                        shape._element.getparent().remove(shape._element)
                        slide.shapes.add_picture(tmp, left, top, width=width, height=height)
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                    vervangen += 1

                elif kind == "fill":
                    if ratio_mode == "cover":
                        w, h = shape.width, shape.height
                        with Image.open(path) as im:
                            cropped = _crop_to_ratio(im, w, h)
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                                cropped.save(tf.name)
                                tmp = tf.name
                        shape.fill.user_picture(tmp)
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                    else:
                        shape.fill.user_picture(path)
                    vervangen += 1

            except Exception as e:
                print(f"Fout: kon foto niet vervangen op dia {s_idx}: {e}")

            foto_idx += 1

    print(f"In totaal {vervangen} foto's vervangen.")
    return vervangen


def zet_titel_dia(prs, naam, datums=None, bijzin=None):
    if not prs.slides:
        return
    slide = prs.slides[0]
    title_shape = None
    subtitle_shape = None

    for sh in slide.shapes:
        if getattr(sh, "is_placeholder", False):
            try:
                if sh.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE):
                    title_shape = sh
                elif sh.placeholder_format.type == PP_PLACEHOLDER.SUBTITLE:
                    subtitle_shape = sh
            except Exception:
                pass

    if title_shape is not None and hasattr(title_shape, "text_frame"):
        title_shape.text_frame.clear()
        title_shape.text_frame.text = naam

    subtitle_lines = []
    if datums:
        subtitle_lines.append(datums)
    if bijzin:
        subtitle_lines.append(bijzin)

    if subtitle_shape is not None and hasattr(subtitle_shape, "text_frame"):
        subtitle_shape.text_frame.clear()
        subtitle_shape.text_frame.text = "\n".join(subtitle_lines)


def maak_presentatie_automatisch(
    sjabloon_pad,
    upload_bestanden,
    uitvoer_pad="uitvaart_presentatie_resultaat.pptx",
    ratio_mode="cover",
    titel_naam=None,
    titel_datums=None,
    titel_bijzin=None
):
    if not os.path.exists(sjabloon_pad):
        raise FileNotFoundError(f"Sjabloon niet gevonden: {sjabloon_pad}")
    if not upload_bestanden:
        raise ValueError("Er zijn geen geüploade bestanden gevonden.")

    tmp_dir = tempfile.mkdtemp(prefix="uploads_")
    print(f"Tijdelijke map aangemaakt: {tmp_dir}")

    fotopaden = []

    try:
        zip_bestanden = [f for f in upload_bestanden if f.lower().endswith(".zip")]
        if zip_bestanden:
            print("ZIP-bestand gevonden, wordt uitgepakt...")
            for zip_pad in zip_bestanden:
                with zipfile.ZipFile(zip_pad, "r") as zip_ref:
                    zip_ref.extractall(tmp_dir)
            fotopaden = verzamel_fotobestanden(tmp_dir)
        else:
            print("Losse foto's gevonden, worden direct gebruikt...")
            for f in upload_bestanden:
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    doelpad = os.path.join(tmp_dir, os.path.basename(f))
                    shutil.copy(f, doelpad)
                    fotopaden.append(doelpad)

        if not fotopaden:
            raise ValueError("Geen geldige foto's gevonden na upload of uitpakken.")

        prs = Presentation(sjabloon_pad)

        if titel_naam:
            zet_titel_dia(prs, titel_naam, titel_datums, titel_bijzin)

        vervang_alle_fotos(prs, fotopaden, ratio_mode=ratio_mode)

        output_path = os.path.join(os.path.dirname(__file__), uitvoer_pad)
        prs.save(output_path)
        print(f"Presentatie opgeslagen als: {output_path}")
        return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("Tijdelijke bestanden verwijderd.")
