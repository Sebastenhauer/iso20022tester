from typing import Optional

from pydantic import BaseModel


class AppConfig(BaseModel):
    output_path: str = "./output"
    xsd_path: str = "schemas/pain.001.001.09.ch.03.xsd"
    seed: Optional[int] = None
    report_format: str = "docx"
