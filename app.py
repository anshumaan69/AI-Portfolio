# imports

from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr


# The usual start
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
google_api_key = os.getenv("GOOGLE_API_KEY")

if not google_api_key:
    print("❌ WARNING: GOOGLE_API_KEY not found in environment variables!")
    print("Please set GOOGLE_API_KEY in your Hugging Face Space secrets.")
    # Create a dummy client to prevent errors, but it won't work
    gemini = None
else:
    gemini = OpenAI(base_url=GEMINI_BASE_URL, api_key=google_api_key)


# For pushover

pushover_user = os.getenv("PUSHOVER_USER")
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_url = "https://api.pushover.net/1/messages.json"


# Debug: Check if Pushover credentials are loaded
print(f"Pushover User: {pushover_user[:10] if pushover_user else 'NOT SET'}...")
print(f"Pushover Token: {pushover_token[:10] if pushover_token else 'NOT SET'}...")
print(f"Pushover URL: {pushover_url}")

if not pushover_user or not pushover_token:
    print("❌ PROBLEM: Pushover credentials are not set!")
    print("Make sure you have PUSHOVER_USER and PUSHOVER_TOKEN in your .env file")
    print("Push notifications will be disabled.")
    PUSHOVER_ENABLED = False
else:
    print("✅ Pushover credentials are loaded")
    PUSHOVER_ENABLED = True


def push(message):
    print(f"Push: {message}")
    if PUSHOVER_ENABLED:
        payload = {"user": pushover_user, "token": pushover_token, "message": message}
        try:
            requests.post(pushover_url, data=payload)
        except Exception as e:
            print(f"Failed to send push notification: {e}")
    else:
        print("Push notifications are disabled")


# Test push notification (commented out for production)
# push("HEY!!")


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording interest from {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}


def record_unknown_question(question):
    push(f"Recording {question} asked that I couldn't answer")
    return {"recorded": "ok"}


record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}




record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}



tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]



tools



# This function can take a list of tool calls, and run them. This is the IF statement!!

def handle_tool_calls(tool_calls):
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        print(f"Tool called: {tool_name}", flush=True)

        # THE BIG IF STATEMENT!!!

        if tool_name == "record_user_details":
            result = record_user_details(**arguments)
        elif tool_name == "record_unknown_question":
            result = record_unknown_question(**arguments)

        results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
    return results



# Test function call (commented out for production)
# globals()["record_unknown_question"]("this is a really hard question")



reader = PdfReader("me/Agenticme.pdf")
linkedin = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        linkedin += text

with open("me/summary.txt", "r", encoding="utf-8") as f:
    summary = f.read()

name = "Anshumaan Mishra"


system_prompt = f"You are acting as {name}. You are answering questions on {name}'s website, \
particularly questions related to {name}'s career, background, skills and experience. \
Your responsibility is to represent {name} for interactions on the website as faithfully as possible. \
You are given a summary of {name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

system_prompt += f"\n\n## Summary:\n{summary}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
system_prompt += f"With this context, please chat with the user, always staying in character as {name}."





def chat(message, history):
    if gemini is None:
        return "❌ Sorry, the AI assistant is not available. Please contact the administrator to set up the Google API key."
    
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
    done = False
    while not done:
        try:
            # This is the call to the LLM - see that we pass in the tools json
            response = gemini.chat.completions.create(model="gemini-2.0-flash", messages=messages, tools=tools)

            finish_reason = response.choices[0].finish_reason
            
            # If the LLM wants to call a tool, we do that!
             
            if finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = handle_tool_calls(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        except Exception as e:
            print(f"Error in chat: {e}")
            return f"❌ Sorry, I encountered an error: {str(e)}"
    
    return response.choices[0].message.content


gr.ChatInterface(chat, type="messages").launch()