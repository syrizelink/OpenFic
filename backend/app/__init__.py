import os
import warnings

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
warnings.filterwarnings(
    "ignore",
    message="The default value of `allowed_objects` will change in a future version.*",
    category=LangChainPendingDeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"encoding_format is not default parameter.*",
    category=UserWarning,
)
