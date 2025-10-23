# scripts/maak_presentatie.py
# -*- coding: utf-8 -*-
"""
Warme Uitvaartassistent — Automatische PowerPoint-bouwer met placeholder-herkenning

Belangrijkste features:
- Vervangt afbeeldingen in een .pptx-sjabloon op basis van shape-namen: foto_1, foto_2, ...
- Houdt alle overgangen/animaties en lay-out intact (we vervangen alleen de afbeeldingen)
- Ondersteunt Base44-URL's (download), maar ook lokale uploads en ZIP-archieven (voor testen)
- Herhaalt foto's automatisch als er minder foto's zijn dan placeholders
- Kan de titel-dia invullen (naam, datums, bijzin)
- Ondersteunt ratio_mode:
    * "cover": vullend (cropt de foto zodat de shape gevuld wordt)
    * "fit"  : contain (past de foto binnen de shape zonder croppen)
"""

import os
import re
import io
import zipfile
import tempfile
import shutil
import requests
import streamlit as st

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.dml import MSO_FILL
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.util import Emu
from PIL import Image


# ---------------------------
# Helpers voor bestanden/foto's
# ---------------------------

def verzamel_fotobestanden(uploadmap: str) -> list[str]:
    """Zoek alle .jpg/.jpeg/.png in een map (recursief)."""
    fotopaden = []
    for root, _, files in os.walk(uploadmap):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                fotopaden.append(os.path.join(root, f))
    return fotopaden


def download_base44_fotos(foto_urls: list[str], tmp_dir: str) -> list[str]:
    """
    Download alle Base44-foto's (via URL) naar tmp_dir en retourneer een lijst paden.
    Deze versie is stabieler: bevat retries, timeouts en foutafhandeling.
    """
    import time
    paden = []

    print("🪶 Debug: start downloaden van Base44-foto’s...")

    for i, url in enumerate(foto_urls, start=1):
        success = False
        for attempt in range(3):  # probeer max 3 keer
            try:
                print(f"➡️ Download poging {i} (poging {attempt+1}/3):", url)
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    ext = ".jpg"
                    ct = r.headers.get("Content-Type", "")
                    if "png" in ct.lower():
                        ext = ".png"
                    pad = os.path.join(tmp_dir, f"base44_foto_{i}{ext}")
                    with open(pad, "wb") as f:
                        f.write(r.content)
                    print(f"✅ Foto {i} opgeslagen als:", pad)
                    paden.append(pad)
                    success = True
                    break
                else:
                    print(f"⚠️ Foto {i}: status {r.status_code}, probeer opnieuw...")
            except Exception as e:
                print(f"❌ Fout bij foto {i} (poging {attempt+1}):", e)
            time.sleep(1)

        if not success:
            print(f"🚫 Foto {i} kon niet worden gedownload na 3 pogingen.")

    print(f"✅ In totaal {len(paden)} foto's succesvol gedownload.")
    return paden


# ---------------------------
# Beeldverwerking
# ---------------------------

def _compute_contain_size(img_w: int, img_h: int, box_w_emu: Emu, box_h_emu: Emu) -> tuple[int, int]:
    """
    Bereken contain (fit) afmetingen in pixels binnen een shape-box (EMU → relatieve verhouding).
    We gebruiken alleen verhoudingen, dus EMU-naar-pixels conversie is niet strikt nodig;
    zolang het consistent is, klopt de ratio.
    """
    box_w = int(box_w_emu)
    box_h = int(box_h_emu)
    r = min(box_w / img_w, box_h / img_h)
    return max(1, int(img_w * r)), max(1, int(img_h * r))


def _crop_to_ratio(img: Image.Image, target_w_emu: Emu, target_h_emu: Emu) -> Image.Image:
    """
    Crop de afbeelding zodat hij 'cover' vult binnen de gegeven box (EMU).
    We croppen op basis van verhoudingen (geen absolute dpi nodig).
    """
    img_w, img_h = img.size
    target_ratio = float(target_w_emu) / float(target_h_emu)
    img_ratio = img_w / img_h

    if img_ratio > target_ratio:
        # Beeld is breder dan doel → crop links/rechts
        new_w = int(target_ratio * img_h)
        x0 = (img_w - new_w) // 2
        return img.crop((x0, 0, x0 + new_w, img_h))
    else:
        # Beeld is hoger dan doel → crop boven/onder
        new_h = int(img_w / target_ratio)
        y0 = (img_h - new_h) // 2
        return img.crop((0, y0, img_w, y0 + new_h))


# ---------------------------
# Placeholder-detectie en vervanging
# ---------------------------

_PLACEHOLDER_RE = re.compile(r"^foto_(\d+)$", re.IGNORECASE)


def _iter_all_shapes_recursive(container):
    """
    Itereer alle shapes, inclusief shapes in groepen (recursief).
    """
    for sh in container.shapes:
        yield sh
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            # Recurse in group
            for inner in _iter_all_shapes_recursive(sh):
                yield inner


def _collect_named_placeholders(prs: Presentation) -> list[tuple[int, object]]:
    """
    Vind alle shapes in de presentatie met naam 'foto_<nummer>'.
    Retourneert lijst tuples: (index, shape) waarbij index = int(<nummer>).
    """
    matches = []
    for slide in prs.slides:
        for sh in _iter_all_shapes_recursive(slide):
            nm = getattr(sh, "name", None)
            if not nm:
                continue
            m = _PLACEHOLDER_RE.match(nm)
            if m:
                idx = int(m.group(1))
                matches.append((idx, sh))
    # Sorteer op index (foto_1, foto_2, ...)
    matches.sort(key=lambda t: t[0])
    return matches


def _replace_shape_with_picture(slide, shape, image_path: str, ratio_mode: str = "cover"):
    """
    Vervang de visuele inhoud van een shape door image_path, met behoud van positie/afmetingen.
    - Als het een PICTURE-placeholder is, gebruik insert_picture.
    - Als het een gewone PICTURE-shape is, verwijder en voeg nieuw picture toe op dezelfde bounds.
    - Als het een shape met PICTURE-fill is, vervang de fill.user_picture (optioneel met crop).
    """
    left, top, width, height = shape.left, shape.top, shape.width, shape.height

    # 1) Placeholder (type PICTURE)
    if getattr(shape, "is_placeholder", False):
        try:
            if shape.placeholder_format.type == PP_PLACEHOLDER.PICTURE:
                # insert_picture behoudt de placeholder-positie en -verhouding
                if ratio_mode == "fit":
                    # Bij fit: we laten PowerPoint het plaatsen; evt. vooraf resizen
                    shape.insert_picture(image_path)
                else:
                    # Bij cover: we croppen vooraf naar box-verhouding
                    with Image.open(image_path) as im:
                        cropped = _crop_to_ratio(im, width, height)
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                            cropped.save(tf.name)
                            tmp = tf.name
                    shape.insert_picture(tmp)
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                return
        except Exception:
            # Valt door naar algemene logica
            pass

    # 2) Picture-shape (bitmap)
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        if ratio_mode == "fit":
            # contain → nieuw picture gecentreerd binnen bounds
            with Image.open(image_path) as im:
                new_w_px, new_h_px = _compute_contain_size(im.width, im.height, width, height)
            new_left = left + Emu((width - new_w_px) // 2)
            new_top = top + Emu((height - new_h_px) // 2)
            shape._element.getparent().remove(shape._element)
            slide.shapes.add_picture(image_path, new_left, new_top,
                                     width=Emu(new_w_px), height=Emu(new_h_px))
        else:
            # cover → vooraf croppen en exact in de box plaatsen
            with Image.open(image_path) as im:
                cropped = _crop_to_ratio(im, width, height)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    cropped.save(tf.name)
                    tmp = tf.name
            shape._element.getparent().remove(shape._element)
            slide.shapes.add_picture(tmp, left, top, width=width, height=height)
            try:
                os.remove(tmp)
            except Exception:
                pass
        return

    # 3) Shape met picture-fill
    try:
        if shape.fill.type == MSO_FILL.PICTURE:
            if ratio_mode == "cover":
                with Image.open(image_path) as im:
                    cropped = _crop_to_ratio(im, width, height)
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                        cropped.save(tf.name)
                        tmp = tf.name
                shape.fill.user_picture(tmp)
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            else:
                shape.fill.user_picture(image_path)
            return
    except Exception:
        pass

    # 4) Fallback: verwijder en voeg als picture toe op dezelfde bounds
    try:
        shape._element.getparent().remove(shape._element)
    except Exception:
        # Als verwijderen niet lukt, proberen we gewoon te plaatsen erbovenop
        pass

    if ratio_mode == "fit":
        with Image.open(image_path) as im:
            new_w_px, new_h_px = _compute_contain_size(im.width, im.height, width, height)
        new_left = left + Emu((width - new_w_px) // 2)
        new_top = top + Emu((height - new_h_px) // 2)
        slide.shapes.add_picture(image_path, new_left, new_top,
                                 width=Emu(new_w_px), height=Emu(new_h_px))
    else:
        with Image.open(image_path) as im:
            cropped = _crop_to_ratio(im, width, height)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                cropped.save(tf.name)
                tmp = tf.name
        slide.shapes.add_picture(tmp, left, top, width=width, height=height)
        try:
            os.remove(tmp)
        except Exception:
            pass


def vervang_placeholder_fotos(prs: Presentation,
                              fotopaden: list[str],
                              ratio_mode: str = "cover",
                              repeat_if_insufficient: bool = True) -> int:
    """
    Vervang alle placeholders (foto_1, foto_2, ...) in de presentatie met foto's uit fotopaden.
    - Als er minder foto's zijn dan placeholders en repeat_if_insufficient=True,
      herhalen we de lijst (1→n, 2→n+1, ...)
    - Retourneert het aantal vervangen placeholders.
    """
    placeholders = _collect_named_placeholders(prs)
    if not placeholders:
        print("Geen placeholders met naam foto_x gevonden in sjabloon.")
        return 0

    if not fotopaden:
        print("Geen fotopaden aangeleverd voor vervanging.")
        return 0

    totaal_fotos = len(fotopaden)
    vervangen = 0

    for i, (_, shape) in enumerate(placeholders):
        if i < totaal_fotos:
            foto_pad = fotopaden[i]
        else:
            if repeat_if_insufficient:
                foto_pad = fotopaden[i % totaal_fotos]
            else:
                # Geen herhaling — placeholder overslaan
                continue

        try:
            # slide referentie nodig om add_picture te kunnen callen
            slide = shape.part.slides[shape._element.getparent().getparent().index]
        except Exception:
            # Robuuste manier om de slide te vinden:
            # loop even door alle slides om te zien waar de shape bij hoort
            slide = None
            for s in prs.slides:
                for sh in s.shapes:
                    if sh == shape:
                        slide = s
                        break
                if slide:
                    break

        try:
            if slide is None:
                # Als slide niet gevonden is, proberen we een generieke vervanging
                slide = prs.slides[0]
            _replace_shape_with_picture(slide, shape, foto_pad, ratio_mode=ratio_mode)
            vervangen += 1
        except Exception as e:
            nm = getattr(shape, "name", "onbekend")
            print(f"Kon foto niet vervangen bij {nm}: {e}")

    print(f"In totaal {vervangen} placeholders vervangen.")
    return vervangen


# ---------------------------
# Titel-dia
# ---------------------------

def zet_titel_dia(prs: Presentation, naam: str, datums: str | None = None, bijzin: str | None = None):
    """
    Vul de eerste slide (indien aanwezig) met titel/ondertitel.
    Zoekt TITLE/CENTER_TITLE/SUBTITLE placeholders.
    """
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


# ---------------------------
# Hoofdfunctie
# ---------------------------

def maak_presentatie_automatisch(
    sjabloon_pad: str,
    base44_foto_urls: list[str] | None = None,
    upload_bestanden: list[str] | None = None,
    uitvoer_pad: str = "uitvaart_presentatie_resultaat.pptx",
    ratio_mode: str = "cover",  # "cover" of "fit"
    titel_naam: str | None = None,
    titel_datums: str | None = None,
    titel_bijzin: str | None = None,
    repeat_if_insufficient: bool = True
) -> str:
    """
    Bouw een presentatie op basis van:
      - sjabloon_pad: pad naar .pptx-sjabloon
      - base44_foto_urls: lijst met foto-URL's (voorkeur, productie)
      - upload_bestanden: lokale paden of .zip (voor testen)
    Slaat het resultaat op naast dit script (standaardnaam 'uitvaart_presentatie_resultaat.pptx').
    Retourneert het volledige output-pad.
    """
    if not os.path.exists(sjabloon_pad):
        raise FileNotFoundError(f"Sjabloon niet gevonden: {sjabloon_pad}")

    if not base44_foto_urls and not upload_bestanden:
        raise ValueError("Geen invoer: geef base44_foto_urls of upload_bestanden op.")

    tmp_dir = tempfile.mkdtemp(prefix="presentatie_")
    print(f"Tijdelijke map aangemaakt: {tmp_dir}")

    fotopaden: list[str] = []

    try:
        # 1) Base44-URLs (productiepad)
        if base44_foto_urls:
            print("Download Base44-foto's...")
            fotopaden = download_base44_fotos(base44_foto_urls, tmp_dir)

        # 2) (Optioneel) Lokale bestanden/ZIP (voor testen)
        if upload_bestanden and not fotopaden:
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
            raise ValueError("Geen geldige foto's gevonden om te verwerken.")

        # 3) Laad sjabloon en zet optioneel titel-dia
        prs = Presentation(sjabloon_pad)
        if titel_naam:
            zet_titel_dia(prs, titel_naam, titel_datums, titel_bijzin)

        # 4) Vervang placeholders op naam (met herhalen indien nodig)
        vervang_placeholder_fotos(
            prs,
            fotopaden,
            ratio_mode=ratio_mode,
            repeat_if_insufficient=repeat_if_insufficient
        )

        # 🧭 Debug: toon hoeveel placeholders zijn gevonden
        try:
           placeholders = _collect_named_placeholders(prs)
           print("DEBUG: Gevonden placeholders in sjabloon:")
           st.write("🧭 DEBUG: Gevonden placeholders in sjabloon:")

           for idx, sh in enumerate(placeholders, start=1):
             print(f" - naam: foto_{idx}, shape_type: {getattr(sh, 'shape_type', 'onbekend')}")
             st.write(f"• Naam: foto_{idx}, type: {getattr(sh, 'shape_type', 'onbekend')}")

           if not placeholders:
             print("⚠️ Geen placeholders met naam foto_x gevonden in sjabloon!")
             st.warning("⚠️ Geen placeholders met naam foto_x gevonden in sjabloon!")

        except Exception as e:
           print(f"❌ Fout bij debuggen van placeholders: {e}")
           st.error(f"❌ Fout bij debuggen van placeholders: {e}")


        # 5) Opslaan
        base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
        output_path = os.path.join(base_dir, uitvoer_pad)
        prs.save(output_path)
        print(f"Presentatie opgeslagen als: {output_path}")
        print("✅ Functie klaar, pad geretourneerd:", output_path)
        return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("Tijdelijke bestanden verwijderd.")