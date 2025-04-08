from openai import OpenAI

client = OpenAI()


# Setup OpenApi key in the environment like this:
# export OPENAI_API_KEY=sk-...
# Or define it here (not save):
# openai.api_key = "sk-..."


def read_prompt(file_name):
    with open(file_name, "r") as file:
        content = file.read()
        return content


prompt = read_prompt("prompt.txt")


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
