import os
import time
import csv
import logging
import pandas as pd
import anthropic
import re
from colorlog import ColoredFormatter
from openai import OpenAI


class Analyser:
    patterns = [
        re.compile(r"^\s*```(?:json|jsonc)?\s*\r?\n([\s\S]*?)\r?\n```\s*$", re.IGNORECASE),
        re.compile(r"^\s*'''(?:json|jsonc)?\s*\r?\n([\s\S]*?)\r?\n'''\s*$", re.IGNORECASE),
        re.compile(r"^\s*~~~(?:json|jsonc)?\s*\r?\n([\s\S]*?)\r?\n~~~\s*$", re.IGNORECASE),
        re.compile(r"^\s*```(?:json|jsonc)?\s*([\s\S]*?)\s*```\s*$", re.IGNORECASE),
        re.compile(r"^\s*'''(?:json|jsonc)?\s*([\s\S]*?)\s*'''\s*$", re.IGNORECASE),
        re.compile(r"^\s*~~~(?:json|jsonc)?\s*([\s\S]*?)\s*~~~\s*$", re.IGNORECASE),
    ]

    master_prompt = '''
    You are a data analysis expert. Your task is to classify a given website's privacy policy into six categories:
    
    - types – categories of data collected
    - purposes – why data is collected and how it is used 
    - retention period – how long data is stored before deletion or anonymisation
    - sharing – third‑party recipients (list of names)
    - rights – user rights and controls 
    - contact – contact methods mentioned for enquiries/support/further information (only methods, not specific contact details)
    
    Instructions
    1. Read the policy carefully.
    Review every sentence to understand what is and isn’t stated and remove anything that cannot be associated with a privacy statement/privacy policy.
    2. Analyze sentence by sentence.
    - Tag ONLY explicit mentions.
    - For each category, note what is declared:
    - If no information appears, use "Not mentioned".
    - If a category is referenced but no details are given, use "Mentioned but not disclosed".
    3. Internally reason with Chain of Thought.
    - Before presenting the JSON, think without printing in the following manner:
    
    Sentence 1: "We collect your name and email address." → types: ['name', 'email']
    Sentence 4: "Data is stored for up to 30 days." → retention period: ['30 days']
    Sentence 7: "You may opt out by emailing support." → rights: ['opt-out'], contact: ['email']
    Sentence 11: "Data is shared with third parties." → sharing: ['Mentioned but not disclosed']
    
    4. Ignore mentions in hypothetical or negated contexts, e.g., "we 
     do NOT collect ...", or text that can be classified as noise, such as a word that does not fit the context such as one line words
    
    5. Report your final answer in this exact JSON format:
    {
      "types":     [...],
      "purposes":  [...],
      "retention": [...],
      "sharing":   [...],
      "rights":    [...],
      "contact":   [...]
    }
    Lists must be comma-separated arrays of strings.
    
    Preserve the order of appearance but dedupe identical items.
    6. If the text does look like a scraping error or is not present the output must still be in json with the types completed accordingly, i.e. if all are missing, all classes will be "Not mentioned"
    
    Glossary (examples only—non‑exhaustive)
    data types: name, email, phone number, postal address, IP address, browsing history, biometric info, device identifiers, purchase history, etc.
    purposes: Basic functioning, User experience, Statistics and research, Security, Legal requirements, Marketing, Sharing, etc.
    retention: 30 days, 90 days, indefinite, etc.
    sharing: Acme Corp., ad‑partners.com, government agencies, etc.
    rights: access, edit, delete, opt‑in, opt‑out, deactivate, etc.
    contact: email, phone number, fax, postal address, live chat, etc.
    
    Below is a complete example:
    Section of a privacy policy, which also contains noise added: 
    "cookies
    english
    address
    We collect your name, device ID, and purchase history. We share information with Acme Corp. Data is stored for 90 days. You can request deletion by emailing us.
    location: 1st downs street
    ice cream
    "
    - "We collect name, device ID, purchase history."  
      → types: ['name', 'device ID', 'purchase history']
    
    - "We share information with Acme Corp."  
      → sharing: ['Acme Corp']
    
    - "Data is stored for 90 days."  
      → retention period: ['90 days']
    
    - "You can request deletion by emailing us."  
      → rights: ['delete'], contact: ['email']
    
    
    This is the ONLY way the output should look like:
     "{ 
      "types":     ["name", "device ID", "purchase history"],
      "purposes":  ["Not mentioned"],
      "retention period": ["90 days"],
      "sharing":   ["Acme Corp"],
      "rights":    ["delete"],
      "contact":   ["email", ''location"]
    }"
    '''

    anthropic_model = "claude-3-sonnet-latest"
    openai_model = "gpt-4o"
    deepseek_model = "deepseek/deepseek-r1-0528-qwen3-8b:free"
    deepseek_model_r3 = "deepseek/deepseek-chat-v3-0324:free"
    deepseek_R1T2 = "tngtech/deepseek-r1t2-chimera:free"

    def __init__(self, privacy_policy, model = "OpenAI"):
        # Set the privacy policy text
        self.privacy_policy = privacy_policy

        # Set the model
        self.model = model

        # Configuration for GPT
        if self.model == "OpenAI":
            # Get OpenAI API key
            self.api_key = os.getenv("OPENAI_API_KEY")

        elif self.model == "Anthropic":
            # Get OpenAI API key
            self.api_key = os.getenv("ANTHROPIC_API_KEY")

        elif self.model == "DeepSeek":
            # Get DeepSeek API
            self.api_key = os.getenv("DEEPSEEK_API_KEY")

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
            response_format={"type": "json_object"},
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
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)

        # Send prompt and create response
        response = client.chat.completions.create(
            model = self.deepseek_R1T2,
            temperature=0.0,
            presence_penalty=0.3,
            messages=[
                {"role": "system", "content": self.master_prompt},
                {"role": "user", "content": self.privacy_policy}
            ]
        )

        reply = response.choices[0].message.content

        return reply

    def unwrap_json_fence(self, text):
        for pat in self.patterns:
            m = pat.search(text)
            if m:
                return m.group(1).strip()
        return text.strip()

    def save_annotated_to_csv(self,domain,privacy_url,policy_text,annotation,filename='../../datasets/out-Alexa/policy_annotated_output.csv'):
        """
        Append a row to the annotated output CSV with:
          - Input Domain
          - Privacy Policy URL (or 'Not Found')
          - Policy Text
          - Annotation
          - Needs Review (bool or str)

        Writes the header row if the file does not yet exist.

        :param domain: The domain that was scraped (e.g., 'example.com')
        :param privacy_url: The full URL of the privacy policy page, or None
        :param policy_text: The extracted text of the privacy policy
        :param annotation:   The analysis/annotation text returned by your model
        :param needs_review: Bool or string flag (defaults to False)
        :param filename:     Path to the CSV output file
        """
        file_exists = os.path.isfile(filename)

        # ensure output directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Write header only once
            if not file_exists:
                writer.writerow(['Input Domain', 'Privacy Policy URL', 'Policy Text', 'Annotation'])

            writer.writerow([domain, privacy_url or 'Not Found', str(policy_text).strip(), annotation ])

    #TODO: This is used twice now in main an in here, pipelines are not connected because of bulk analysis
    def configure_logger():
        """
            Sets up global logging configuration with a custom "DETAIL" level (15),
            and applies colored output for console logs.

            - DETAIL messages appear in blue
            - INFO messages appear in green
            - DEBUG, WARNING, ERROR, CRITICAL get their own associated colors
        """
        # Define and register a new log level DETAIL (between DEBUG=10 and INFO=20)
        DETAIL_LEVEL_NUM = 15
        logging.addLevelName(DETAIL_LEVEL_NUM, "DETAIL")
        logging.Logger.detail = (
            lambda self, message, *args, **kwargs:
            self._log(DETAIL_LEVEL_NUM, message, args, **kwargs)
            if self.isEnabledFor(DETAIL_LEVEL_NUM) else None
        )

        # Basic configuration: console and file handlers, capturing DETAIL
        logging.basicConfig(
            level=DETAIL_LEVEL_NUM,  # Or DEBUG for more verbose output
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),  # Output to console
                logging.FileHandler('../../datasets/out-Alexa/analyser.log', mode='w')  # Output to file
            ]
        )

        # Define colored format and color mapping for log levels
        colored_fmt = (
            "%(log_color)s"  # injects the color code
            "%(asctime)s - %(levelname)-8s - %(message)s"
            "%(reset)s"  # resets color back to normal
        )
        color_map = {
            'DETAIL': 'blue',
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
        color_formatter = ColoredFormatter(
            colored_fmt,
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors=color_map,
            reset=True
        )

        # Replace formatter on console handler only
        root = logging.getLogger()
        for handler in root.handlers:
            # only colorize real console handlers, not the file handler
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setFormatter(color_formatter)


if __name__ == '__main__':
    # TODO: REMOVE
    # OpenAI
    # analyser = Analyser(privacy_policy="This is a privacy policy", model="OpenAI")
    # Anthropic
    # analyser = Analyser(privacy_policy="This is a privacy policy", model="Anthropic")
    # DeepSeek (interestingly works with OpenAI API)
    # analyser = Analyser(privacy_policy="This is a privacy policy", model="DeepSeek")

    Analyser.configure_logger()
    # Setup logger for this module
    logger = logging.getLogger(__name__)

    scraped_data = pd.read_csv("../../datasets/out-Alexa/policy_scrape_output.csv")
    logger.info("Scraped data loaded.")

    filtered_scraped_data = filtered = scraped_data[scraped_data['Policy Text'] != 'No privacy url found']
    logger.detail("Scraped data curated of outdated domains, non-English domains, and unsuccessful scrapes.")
    logger.detail("Starting iterative analysis...")

    start_idx = 2094

    for idx, row in filtered_scraped_data.iterrows():
        if idx < start_idx:
            continue

        logger.info(f"Started analysis for {row['Input Domain']} and index {idx}.")
        analyser = Analyser(privacy_policy=row['Policy Text'], model="DeepSeek")
        logger.detail(f"Analyser initialised with model: DeepSeek.")

        try:
            policy_analysis = analyser.analyse_privacy_policy_DeepSeek()
            logger.detail(f"Policy analysis complete.")

            analyser.save_annotated_to_csv(
                domain=row['Input Domain'],
                privacy_url=row['Privacy Policy URL'],
                policy_text=row['Policy Text'],
                annotation=analyser.unwrap_json_fence(policy_analysis),
            )

            logger.detail(f"Analysis completed and saved for {row['Input Domain']}.")
        except Exception as e:
            analyser.save_annotated_to_csv(
                domain=row['Input Domain'],
                privacy_url=row['Privacy Policy URL'],
                policy_text=row['Policy Text'],
                annotation= f"Error occurred during analysis: {e}.",
            )
            logger.error(f"Error occurred during analysis: {e}.")
