from pathlib import Path

import shutil

assets_dir = Path(__file__).parent.parent.parent / "assets"


def configure_ocr_model():
    ocr_src = assets_dir / "MaaCommonAssets" / "OCR" / "ppocr_v4" / "zh_cn"
    ocr_dst = assets_dir / "resource" / "model" / "ocr"

    if not ocr_src.exists():
        print(f"OCR 模型源目录不存在: {ocr_src}")
        exit(1)

    shutil.copytree(
        ocr_src,
        ocr_dst,
        dirs_exist_ok=True,
    )


if __name__ == "__main__":
    configure_ocr_model()
