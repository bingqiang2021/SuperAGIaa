from typing import Type, Optional, List

from pydantic import BaseModel, Field
from superagi.config.config import get_config
from superagi.agent.agent_prompt_builder import AgentPromptBuilder
import os

from superagi.helper.token_counter import TokenCounter
from superagi.llms.base_llm import BaseLlm
from superagi.resource_manager.manager import ResourceManager
from superagi.tools.base_tool import BaseTool
from superagi.lib.logger import logger
from superagi.models.db import connect_db
from superagi.helper.resource_helper import ResourceHelper
from superagi.helper.s3_helper import S3Helper
from sqlalchemy.orm import sessionmaker


class WriteSpecSchema(BaseModel):
    task_description: str = Field(
        ...,
        description="Specification task description.",
    )

    spec_file_name: str = Field(
        ...,
        description="Name of the file to write. Only include the file name. Don't include path."
    )

class WriteSpecTool(BaseTool):
    """
    Used to generate program specification.

    Attributes:
        llm: LLM used for specification generation.
        name : The name of tool.
        description : The description of tool.
        args_schema : The args schema.
        goals : The goals.
        resource_manager: Manages the file resources
    """
    llm: Optional[BaseLlm] = None
    agent_id: int = None
    name = "WriteSpecTool"
    description = (
        "A tool to write the spec of a program."
    )
    args_schema: Type[WriteSpecSchema] = WriteSpecSchema
    goals: List[str] = []
    resource_manager: Optional[ResourceManager] = None

    class Config:
        arbitrary_types_allowed = True

    def _execute(self, task_description: str, spec_file_name: str) -> str:
        """
        Execute the write_spec tool.

        Args:
            task_description : The task description.
            spec_file_name: The name of the file where the generated specification will be saved.

        Returns:
            Generated specification or error message.
        """
        try:
            prompt = """You are a super smart developer who has been asked to make a specification for a program.
        
            Your high-level goal is:
            {goals}
        
            Please keep in mind the following when creating the specification:
            1. Be super explicit about what the program should do, which features it should have, and give details about anything that might be unclear.
            2. Lay out the names of the core classes, functions, methods that will be necessary, as well as a quick comment on their purpose.
            3. List all non-standard dependencies that will have to be used.
        
            Write a specification for the following task:
            {task}
            """
            prompt = prompt.replace("{goals}", AgentPromptBuilder.add_list_items_to_string(self.goals))
            prompt = prompt.replace("{task}", task_description)
            messages = [{"role": "system", "content": prompt}]

            total_tokens = TokenCounter.count_message_tokens(messages, self.llm.get_model())
            token_limit = TokenCounter.token_limit(self.llm.get_model())
            result = self.llm.chat_completion(messages, max_tokens=(token_limit - total_tokens - 100))
            
            # Save the specification to a file
            write_result = self.resource_manager.write_file(spec_file_name, result["content"])
            if not write_result.startswith("Error"):
                return result["content"] + "Specification generated and saved successfully"
            else:
                return write_result
                
        except Exception as e:
            logger.error(e)
            return f"Error generating specification: {e}"