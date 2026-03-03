"""
every major LLM library (OpenAI's SDK, LangChain, Anthropic, etc.) has these 
"standard" message models built-in.

If you are a Java developer, think of this as the difference between using 
a third-party library's POJO directly in your business logic vs. defining 
your own Interface/DTO that wraps it.

Here is why you are likely better off defining them yourself, even if it feels
like "reinventing the wheel":

1. Decoupling (The "Dependency Inversion" Principle)
If you use openai.types.chat.ChatCompletionMessage throughout your entire
application, your code is now permanently coupled to OpenAI's library.
If you decide to switch to Anthropic, Google Gemini, or a local model 
(like Llama via Ollama) in six months, you would have to refactor your 
entire codebase.

Your Way: You define your own BaseMessage hierarchy. You write a small "Adapter"
or "Mapper" that converts your UserMessage into the specific format the AI
provider needs. Your business logic stays pure.

2. Domain-Specific Logic
Standard library classes are "dumb" data containers. By defining your own, 
you can add methods that actually make sense for your business:

my_message.to_sanitized_string(): A method to strip PII before sending it to 
the cloud.

my_message.to_db_format(): A method to map to your specific database schema.

my_message.validate_format(): Your own custom validation rules.

3. Persistence
When you save these messages to a database (to build "memory" for your agent),
do you want to save a proprietary library object that might change 
version-to-version? No. You want to save your schema. Defining these yourself
gives you full control over your serialization/deserialization logic.
"""

from pydantic import BaseModel
from typing import Optional, Union, List, Dict, Any, Literal

class BaseMessage(BaseModel):
    content: Optional[str] = ""

    def dict(self) -> Dict:
        return dict(self)
"""
Literal["system"] is like a strict rule. It tells the AI and the code: 
"The role field for this class must be the string 'system'. You cannot 
change it to 'boss' or 'admin'."
"""
class SystemMessage(BaseMessage) :
    """
        role here is a variable name that is part of the SystemMessage class. 
        It is defined as a Literal type, which means it can only have a 
        specific value. In this case, the only allowed value for role is 
        the string "system". So we create an assined system value to it.
    """
    role: Literal["system"] = "system"

class UserMessage(BaseMessage) :
    role: Literal["user"] = "user"

class ToolMessage(BaseMessage):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str

class AIMessage(BaseMessage):
    role: Literal["assistant"] = "assistant"
    tool_calls: Optional[List[Any]] = None
## Union type allows a variable to hold multiple types of values. In this case,
## AnyMessage can be any one of the message types defined above.
## it holds any of the four message types: SystemMessage, UserMessage, 
# AIMessage, or ToolMessage. But only one of them at a time. 
# This is useful for functions or data structures
## that need to work with different types of messages without knowing 
# in advance which type it will be
AnyMessage = Union[
SystemMessage,
UserMessage,
AIMessage,
ToolMessage,
]