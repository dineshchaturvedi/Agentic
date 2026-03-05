import json
from typing import List, Optional, Dict, Any
from openai import OpenAI
from lib.messages import (
    AIMessage,
    BaseMessage,
    UserMessage,
)

from lib.tooling import Tool

class LLM:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        tools: Optional[List[Tool]] = None,
        api_key: Optional[str] = None
    ):
        self.model = model
        self.temperature = temperature
        ## client variable is created inline and assigned to openAI instance. 
        # If api_key is provided, it will be used to create the OpenAI client;
        # otherwise, a default client will be created.
        self.client = OpenAI(api_key=api_key) if api_key else OpenAI()
        self.tools: Dict[str, Tool] = {
            tool.name: tool for tool in (tools or [])
        }

    def register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def _build_payload(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        payload = {
            # HERE is the definition! We are creating the 'payload' variable.
            "model": self.model, # Key: "model" (str), Value: self.model (str)
            "temperature": self.temperature, # Key: "temperature" (str), Value: 0.0 (float)
            "messages": [m.dict() for m in messages] # Key: "messages" (str), Value: List
        }

        if self.tools: #if a dictionary is empty, it counts as False
            # tool.dict() is needed because LLM only understand 
            # JSON-serializable data, and the Tool class is a Python object.
            payload["tools"] = [tool.dict() for tool in self.tools.values()]
            # Leave the tool_choice as "auto" for now. 
            # This means the LLM will decide which tool to use based on the 
            # input and context.
            payload["tool_choice"] = "auto"

        return payload

    # Job of this functiona is to convert input to list of BaseMessage objects.
    def _convert_input(self, input: Any) -> List[BaseMessage]:
        #isinstance(input, str) is asking if Input is a string. 
        # If it is, we wrap it in a UserMessage and return it as a list.
        if isinstance(input, str):
            return [UserMessage(content=input)]
        elif isinstance(input, BaseMessage):
            return [input]
        elif isinstance(input, list) and all(isinstance(m, BaseMessage) for m in input):
            return input
        else:
            raise ValueError(f"Invalid input type {type(input)}.")
    #In this context, the pipe symbol means "OR" you can pass in a string, 
    # a single BaseMessage, or a list of BaseMessages.
    def invoke(
               self,
               input: str | BaseMessage | List[BaseMessage],
               response_format: Any = None) -> AIMessage:
        messages = self._convert_input(input)
        payload = self._build_payload(messages)
        # **payload is a way to unpack the dictionary into keyword arguments.
        # it looks for the keys in the payload dictionary and passes them as 
        # named arguments to the create method.
        if response_format:
            payload.update({"response_format": response_format})
            response = self.client.beta.chat.completions.parse(**payload)
        else:
            response = self.client.chat.completions.create(**payload)
        # The response object contains a list of choices, and we are 
        # taking the first one. OpenAI sends multiple choices for each request, 
        # but we are only interested in the first one.
        choice = response.choices[0]
        message = choice.message

        content = message.content
        parsed = getattr(message, "parsed", None)
        if parsed is not None:
            if hasattr(parsed, "model_dump"):
                content = json.dumps(parsed.model_dump())
            else:
                content = json.dumps(parsed)

        return AIMessage(
            content=content,
            tool_calls=message.tool_calls
        )
    
