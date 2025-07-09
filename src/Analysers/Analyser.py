import os
import anthropic
from openai import OpenAI

class Analyser:

    master_prompt = 'Just say "hello world" to anything I tell you'

    anthropic_model = "claude-3-sonnet-latest"
    openai_model = "gpt-4o"
    deepseek_model = "deepseek-reasoner"

    def __init__(self, privacy_policy, model = "OpenAI"):
        # Set the privacy policy text
        self.privacy_policy = privacy_policy

        # Set the model
        self.model = model

        # Configuration for GPT
        if self.model == "OpenAI":
            # Get OpenAI API key
            self.api_key = os.getenv("OPENAI_API_KEY")
            # Send for analysis
            self.analyse_privacy_policy_OpenAI()

        elif self.model == "Anthropic":
            # Get OpenAI API key
            self.api_key = os.getenv("ANTHROPIC_API_KEY")
            # Send for analysis
            self.analyse_privacy_policy_Anthropic()

        elif self.model == "DeepSeek":
            # Get DeepSeek API
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
            # Send for analysis
            self.analyse_privacy_policy_DeepSeek()

    def analyse_privacy_policy_OpenAI(self):

        # Set the reply to default empty string
        reply = ''

        # Set the api_key
        client = OpenAI(api_key=self.api_key)

        # Send prompt and create response
        response = client.chat.completions.create(
            # Alternate between OpenAI models here
            model = self.openai_model,
            temperature = 0,
            messages = [
                {"role": "developer", "content": self.master_prompt},
                {"role": "user", "content": self.privacy_policy},
            ],
        )

        # Assign the response to the reply
        reply = response.choices[0].message.content

        return reply

    def analyse_privacy_policy_Anthropic(self):
        # Set the reply to default empty string
        reply = ''

        client = anthropic.Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model = self.anthropic_model,
            max_tokens =  20000,
            temperature = 0,
            system = self.master_prompt,
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self.privacy_policy,
                        }
                    ]
                }
            ]
        )

        reply = message.content

        return reply

    def analyse_privacy_policy_DeepSeek(self):
        # Set the reply to default empty string
        reply = ''

        # Set the api_key
        client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

        # Send prompt and create response
        response = client.chat.completions.create(
            model = self.deepseek_model,
            messages = [
                {"role": "system", "content": self.master_prompt},
                {"role": "user", "content": self.privacy_policy},
            ],
            stream=False
        )


# Test code
# TODO: REMOVE
# OpenAI
# analyser = Analyser(privacy_policy="This is a privacy policy", model="OpenAI")
# Anthropic
# analyser = Analyser(privacy_policy="This is a privacy policy", model="Anthropic")
# DeepSeek (interestingly works with OpenAI API)
analyser = Analyser(privacy_policy="This is a privacy policy", model="DeepSeek")
