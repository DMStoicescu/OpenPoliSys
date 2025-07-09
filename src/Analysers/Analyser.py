import os

from openai import OpenAI
class Analyser:

    master_prompt = ['Just say "hello world" to anything I tell you']

    def __init__(self, privacy_policy, model):
        # Set the privacy policy text
        self.privacy_policy = privacy_policy

        # Set the model
        self.model = model

        # Configuration for GPT
        if self.model == "OpenAI":
            self.api_key = os.getenv("OPENAI_API_KEY")

            self.analyse_privacy_policy_OpenAI


    def analyse_privacy_policy_OpenAI(self):

        # Set the reply to default empty string
        reply = ''

        # If the model OpenAI
        if self.model == "OpenAI":
            # Set the api_key
            client = OpenAI(api_key=self.api_key)

            # Send prompt and create response
            response = client.chat.completions.create(
                # Alternate between OpenAI models here
                model="gpt-4o",
                messages=[
                    {"role": "developer", "content": self.master_prompt},
                    {"role": "user", "content": "How do I check if a Python object is an instance of a class?",
                    },
                ]
            )

            # Assign the response to the reply
            reply = response.choices[0].message.content

        return reply


# Test code
# TODO: REMOVE
# OpenAI
analyser = Analyser(privacy_policy="This is a privacy policy", model="OpenAI")
print(analyser.analyse_privacy_policy_OpenAI)

