from pydantic import BaseModel, ConfigDict


class CloudManagerBaseModel(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)
