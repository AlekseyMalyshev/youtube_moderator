from openai import OpenAI

client = OpenAI()

# openai.api_key = "your-api-key-here"


def read_rules(file_name):
    with open(file_name, "r") as file:
        content = file.read()
        return content


rules = read_rules("channel_rules.txt")

prompt = f"""
You are a chat moderator. Evaluate if the user message violates the rules below:

{rules}

Respond in the json format using the following json schema.
"verdict" is true if the message violates any rule, flase otherwise

```json
{{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {{
        "verdict": {{
        "type": "boolean"
        }}
    }}
}}
```
"""


def evaluate_msg(msg):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": msg},
        ],
        temperature=0,
        max_tokens=100,
    )

    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    pass
