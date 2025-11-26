from groq import Groq
from config import *

async def call_groq_api(chat_history):
    try:
        client = Groq(
            api_key=GROQ_API_KEY,
        )
        
        response = client.chat.completions.create(
            messages=chat_history,
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            temperature=1,
            top_p=1,
            stream=True,
            stop=None,
        )

        full_response = ""

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
        
        return full_response
     
    except Exception as e:
        error_message = f"Error calling Groq API: {str(e)}"
        print(error_message)  # 打印日志
        return "抱歉，我暂时无法处理你的请求。"  # 返回给用户的默认错误消息
    
#             OpenAI(api_key = OPENAI_API_KEY)
#             print(OPENAI_API_KEY)
#             try:
#                 client = OpenAI(
#                      organization="org-jwlTKLr5o8qaeGU1OL0xgt5a",
#                      project="proj_LKwx8mUG90NATGpm7Ub5TB9H"
#                 )

#                 response = client.chat.completions.create(
#                      model="gpt-3.5-turbo", 
#                      messages=chat_history,
#                     temperature=0.7,
#                 )
#                 print(response)
#                 return response["choices"][0]["message"]["content"]
            
#             except Exception as e:
#                 error_message = f"Error calling ChatGPT API: {str(e)}"
#                 print(error_message)  # 打印日志
#                 return "抱歉，我暂时无法处理你的请求。"  # 返回给用户的默认错误消息