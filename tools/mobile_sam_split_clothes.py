#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from mobile_sam import SamPredictor, sam_model_registry


def parse_box(value: str) -> np.ndarray:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x1,y1,x2,y2")
    return np.array(parts, dtype=np.float32)


def parse_points(value: str | None) -> tuple[np.ndarray | None, np.ndarray | None]:
    if not value:
        return None, None

    coords: list[list[float]] = []
    labels: list[int] = []
    for item in value.split(";"):
        if not item.strip():
            continue
        parts = [part.strip() for part in item.split(",")]
        if len(parts) != 3:
            raise argparse.ArgumentTypeError("points must be x,y,label;x,y,label")
        coords.append([float(parts[0]), float(parts[1])])
        labels.append(int(parts[2]))

    if not coords:
        return None, None
    return np.array(coords, dtype=np.float32), np.array(labels, dtype=np.int32)


def alpha_composite_for_sam(image: Image.Image, background=(238, 238, 238)) -> np.ndarray:
    rgba = image.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, background + (255,))
    return np.array(Image.alpha_composite(bg, rgba).convert("RGB"))


def predict_mask(
    predictor: SamPredictor,
    box: np.ndarray,
    points: str | None,
    prefer_score_index: int | None,
) -> np.ndarray:
    point_coords, point_labels = parse_points(points)
    masks, scores, _ = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        box=box,
        multimask_output=True,
    )
    index = int(np.argmax(scores)) if prefer_score_index is None else prefer_score_index
    return masks[index].astype(bool)


def write_layer(source: Image.Image, mask: np.ndarray, output: Path) -> None:
    rgba = np.array(source.convert("RGBA"))
    rgba[:, :, 3] = (rgba[:, :, 3].astype(np.float32) * mask.astype(np.float32)).astype(np.uint8)
    Image.fromarray(rgba, mode="RGBA").save(output)


def write_crop(layer_path: Path, output: Path, padding: int) -> None:
    image = Image.open(layer_path).convert("RGBA")
    bbox = image.getbbox()
    if bbox is None:
        image.save(output)
        return
    left = max(0, bbox[0] - padding)
    top = max(0, bbox[1] - padding)
    right = min(image.width, bbox[2] + padding)
    bottom = min(image.height, bbox[3] + padding)
    image.crop((left, top, right, bottom)).save(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint", default=Path("models/mobile_sam/mobile_sam.pt"), type=Path)
    parser.add_argument("--output-dir", default=Path("processed_assets/mobile_sam"), type=Path)
    parser.add_argument("--top-box", required=True, type=parse_box)
    parser.add_argument("--pants-box", required=True, type=parse_box)
    parser.add_argument("--top-points")
    parser.add_argument("--pants-points")
    parser.add_argument("--top-mask-index", type=int)
    parser.add_argument("--pants-mask-index", type=int)
    parser.add_argument("--crop-padding", default=24, type=int)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    source = Image.open(args.input).convert("RGBA")
    image_for_sam = alpha_composite_for_sam(source)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = sam_model_registry["vit_t"](checkpoint=str(args.checkpoint))
    model.to(device=device)
    model.eval()

    predictor = SamPredictor(model)
    predictor.set_image(image_for_sam)

    top_mask = predict_mask(predictor, args.top_box, args.top_points, args.top_mask_index)
    pants_mask = predict_mask(predictor, args.pants_box, args.pants_points, args.pants_mask_index)

    top_path = args.output_dir / "outfit_top_mobilesam_same_canvas.png"
    pants_path = args.output_dir / "outfit_pants_mobilesam_same_canvas.png"
    recombined_path = args.output_dir / "outfit_recombined_mobilesam_same_canvas.png"

    write_layer(source, top_mask, top_path)
    write_layer(source, pants_mask, pants_path)

    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(pants_path).convert("RGBA"))
    canvas.alpha_composite(Image.open(top_path).convert("RGBA"))
    canvas.save(recombined_path)

    write_crop(top_path, args.output_dir / "outfit_top_mobilesam_crop.png", args.crop_padding)
    write_crop(pants_path, args.output_dir / "outfit_pants_mobilesam_crop.png", args.crop_padding)

    print(f"device={device}")
    print(f"top={top_path}")
    print(f"pants={pants_path}")
    print(f"recombined={recombined_path}")


if __name__ == "__main__":
    main()
