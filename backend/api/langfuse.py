from fastapi import APIRouter

from base.utilities.langfuse_client_utility import LangfuseClientWrapper
from base.utilities.langfuse_prompt_catalog_utility import list_langfuse_prompt_names


router = APIRouter(tags=["langfuse"])


@router.get("/langfuse/prompts")
def get_langfuse_prompts():
    prompts, source, error = list_langfuse_prompt_names()
    return {
        "enabled": LangfuseClientWrapper.get_langfuse_client() is not None,
        "prompts": prompts,
        "source": source,
        "error": error,
    }
