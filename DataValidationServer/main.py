from fastapi import FastAPI, Request,Form,BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, create_model
from typing import Any, List
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import redis.asyncio as redis 
import re
import json
import uuid
import httpx
import asyncio
from google import genai
from jsonschema import validate, ValidationError
import os
from dotenv import load_dotenv,find_dotenv

path=find_dotenv()
load_dotenv(path)

store_model_in_supabase_url = os.getenv("store_model_in_supabase_url")
supabase_service_key        = os.getenv("supabase_service_key")
supabase_admin_table_url    = os.getenv("supabase_admin_table_url")
supabase_iot_history_url    = os.getenv("supabase_iot_history_url")
model_name                  = os.getenv("model_name", "gemini-2.5-flash")
gemini_url                  = os.getenv("gemini_url", f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent")
gemini_api_key              = os.getenv("gemini_api_key")
supabase_redis_table_url    = os.getenv("supabase_redis_table_url")

redis_data_queue=asyncio.Queue()
redis_urls={}
redis_clients={}
async def get_urls():
    print("get urls called")
    global supabase_service_key,supabase_redis_table_url,number_of_redis_instances
    async with httpx.AsyncClient() as client:
        response=await client.get(
            supabase_redis_table_url,
            headers={
                "apikey": supabase_service_key,
                "Authorization": f"Bearer {supabase_service_key}",
                "Accept": "application/json"

            }
            
        )
    print()
    print()
    print("get urls status response:",response.status_code)
    print("response is :",response.json())
    print()
    print()
    if response.status_code in [200,201,204] and response.json()!=[]:
        data=response.json()
        print("Urls found:",data)
        print()
        number_of_redis_instances=len(data)
        return data
    return None


async def redis_instance_health_check(name,url):
    print()
    print()
    print("redis instance hea;th check called")
    print()
    print()
    try:
        global redis_clients
        client=redis.from_url(url=url,decode_responses=True)
        redis_clients[name]=client
        pong=await client.ping()
        print()
        print(name,pong)
        return name,client
    except Exception as e :
        print("Exception happend ",e)
        return name,None

    
async def number_redis_instance_online(redis_urls):
    global redis_clients
    print()
    print()
    print()
    print("number of redis instance online called")
    print("number of redis urls:",len(redis_urls))
    print()
    print()
    tasks=[redis_instance_health_check(name,url) for name,url in redis_urls.items() ]
    print("Tasks",tasks)
    results=await asyncio.gather(*tasks)
    clients={name:value for name,value in results if value is not None}
    print("number of redis instance online called its output",clients)
    return len(clients)


async def put_data_in_supabase_iot_history():
    global store_model_in_supabase_url, supabase_service_key, supabase_iot_history_url

    async with httpx.AsyncClient() as client:
        # Fetch model/schema
        response = await client.get(
            store_model_in_supabase_url,
            headers={
                "apikey": supabase_service_key,
                "Authorization": f"Bearer {supabase_service_key}",
                "Accept": "application/json",
            }
        )
        if response.status_code in [200, 201, 204]:
            model = response.json()[0]["model"]
        else:
            model = None

        # Process Redis queue
        while model:
            try:
                data = await redis_data_queue.get()  # await if async queue

                # Validate
                try:
                    validate(instance=data, schema=model)
                except ValidationError as e:
                    print("Validation failed :", e.message)
                    continue  # skip invalid data

                # Post to Supabase
                response = await client.post(
                    supabase_iot_history_url,
                    headers={
                        "apikey": supabase_service_key,
                        "Authorization": f"Bearer {supabase_service_key}",
                        "Accept": "application/json",
                        "Prefer": "resolution=merge-duplicates"

                    },
                    json=data
                )
                if response.status_code in [200, 201, 204]:
                    print("Data posted successfully ")
                else:
                    print("Failed to post:", response.text)

            except Exception as e:
                print("Exception happened:", e)
async def poll_redis_continuously(poll_interval=1):
    while True:
        for name, client in redis_clients.items():
            try:
                keys = await client.keys("*")
                for key in keys:
                    raw_value = await client.get(key)
                    await client.delete(key)
                    try:
                        value = json.loads(raw_value)  # Convert string -> dict
                        print(f"Pushed to queue from {name}: {value}")
                        await redis_data_queue.put(value)
                    except Exception as e:
                        print(f"Failed to parse Redis value from {name}: {raw_value}", e)
            except Exception as e:
                print(f"Error polling Redis {name}: {e}")
        await asyncio.sleep(poll_interval)

@asynccontextmanager

async def lifespan(app: FastAPI):
    print("\n\nSlave borned\n\n")
    global redis_urls
    redis_url_data = await get_urls()

    if redis_url_data:
        # Prepare redis_urls dictionary
        redis_urls = {
            f"buffer{i}": f"redis://{item['username']}:{item['password']}@{item['url']}:{item['port']}"
            for i, item in enumerate(redis_url_data)
        }

    # Initialize redis clients
    await number_redis_instance_online(redis_urls=redis_urls)

    # Push existing Redis keys into queue
    for name, client in redis_clients.items():
        keys = await client.keys("*")
        for key in keys:
            raw_value = await client.get(key)
            await client.delete(key)
            try:
                value = json.loads(raw_value)  # <-- ensure dict
                print(f"Pushed to queue from {name}: {value}")
                await redis_data_queue.put(value)
            except Exception as e:
                print(f"Failed to parse Redis value {raw_value}: {e}")

    # Start continuous polling and queue processing
    asyncio.create_task(poll_redis_continuously())
    asyncio.create_task(put_data_in_supabase_iot_history())

    yield
    print("Slave has done its task dying")



app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=uuid.uuid5(uuid.NAMESPACE_DNS,"HelloWorld"))
# Allow frontend requests (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust in production
    allow_methods=["*"],
    allow_headers=["*"],
)






async def get_data_for_gemini():
    async with httpx.AsyncClient() as client:
        response=await client.get(
            supabase_iot_history_url,
             headers={"apikey": supabase_service_key,
            "Authorization": f"Bearer {supabase_service_key}"}
        ) 
        if response.status_code in [200,201,204]:
            return response.json()
        else:
            return None

async def get_gemini_response(gemini_prompt):
    async with httpx.AsyncClient() as client:
        try:
            global gemini_api_key,gemini_complete_url
            full_url = f"{gemini_url}?key={gemini_api_key}"
            user_prompt=gemini_prompt
            PAYLOAD = {
                "contents": [
                    {
                    "parts": [
                        {
                        "text": user_prompt
                        }
                    ]
                    }
                ],
                "generationConfig": { # Corrected key from "config" to "generationConfig"
                    "maxOutputTokens": 8192,
                    "temperature": 1.0,
                    "topP": 0.95
                },
                "safetySettings": [
                    {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
                }


            response=await client.post(
                full_url,
                json=PAYLOAD,
                timeout=30.0
                
            )
            response.raise_for_status()
            data= response.json()
            text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No response text found.')
            clean_text=re.sub(r'(\*\*|__|\*|_)', '', text)
            return clean_text
        except Exception as e:
            print("Exception happened:",e)
        


async def store_model_in_supabase(name,model):
    global store_model_in_supabase_url
    async with httpx.AsyncClient() as client:
        response= await client.post(
            store_model_in_supabase_url,
            headers={
                    "apikey": supabase_service_key,
                    "Authorization": f"Bearer {supabase_service_key}",
                    "Accept": "application/json",
                    "Prefer": "resolution=merge-duplicates"
                },
                params={"on_conflict":"name"},
                json={
                    "name":name,
                    "model":model
                }
        )
        print(response.status_code)
        print(response.text)
        if response.status_code in [200,201,204]:
            print("Succesfull posted model ")
        else:
            print("Failed to post data ")


async def get_model_in_supabase():
    print("get response called")
    global store_model_in_supabase_url
    async with httpx.AsyncClient() as client:
        response= await client.get(
            store_model_in_supabase_url,
            headers={
                    "apikey": supabase_service_key,
                    "Authorization": f"Bearer {supabase_service_key}",
                    "Accept": "application/json",
                    },
                
                
        )
        print(response.status_code)
        print(response.text)
        if response.status_code in [200,201,204]:
            print("Succesfull get model ")
            data=response.json()[0]
            
            return data["model"]
        else:
            print("Failed to get data ")
            return None
def encrypt_password(Password:str)->str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS,Password))
async def admin_exists(Username:str)->bool:
    global service_key,supabase_admin_table_url
    async with httpx.AsyncClient() as client:
        response=await client.get(supabase_admin_table_url,
            headers={
                "apikey": supabase_service_key,
                "Authorization": f"Bearer {supabase_service_key}",
                "Accept": "application/json"
            },
            params={"username": f"eq.{Username}"})
        data=response.json() if response.text else []
        print(len(data)>0)
        return len(data)>0
    
async def check_if_admin_valid(Username:str,Password:str)->bool:
    global supabase_service_key,supabase_admin_table_url
    async with httpx.AsyncClient() as client:
        response=await client.get(
            supabase_admin_table_url,
            headers={
                "apikey": supabase_service_key,
                "Authorization": f"Bearer {supabase_service_key}",
                "Accept": "application/json"
            },
            params={"Username": f"eq.{Username}"})
        data = response.json() if response.text else []

        print("data is ",data)
        if not data:
            print("called")
            return False
        print(encrypt_password(Password)==data[0]["Password"])
        if Username==data[0]["Username"] and encrypt_password(Password)==data[0]["Password"]:
            print("Invalid username or password")
            return True  
        return False

templates = Jinja2Templates(directory="templates")

# Pydantic models for incoming request
class FieldData(BaseModel):
    name: str
    type: str
    default: Any = None
    required: bool = False

class ModelRequest(BaseModel):
    model_name: str
    fields: List[FieldData]

@app.get("/create_model", response_class=HTMLResponse)
async def get_create_model_page(request: Request,msg:str=None):
    admin_login = request.session.get("login",False)
    if admin_login:
        request.query_params.get("msg")
        msg=await get_model_in_supabase()
        return templates.TemplateResponse("create_model.html", {"request": request,"response_from_server":msg})
    return RedirectResponse(url="/?msg=Unauthorized+Acess+Denied+Login",status_code=302)

@app.post("/create_model")
async def create_model_endpoint(request:Request,req: ModelRequest):
    admin_login = request.session.get("login",False)
    if admin_login:
        model_name=req.model_name
        type_map = {"str": str, "int": int, "float": float, "bool": bool}
        field_definitions = {}

        for f in req.fields:
            py_type = type_map.get(f.type, str)

            # Convert default to proper type
            default_val = f.default
            if default_val not in (None, ""):
                try:
                    if f.type == "int":
                        default_val = int(default_val)
                    elif f.type == "float":
                        default_val = float(default_val)
                    elif f.type == "bool":
                        if isinstance(default_val, bool):
                            pass
                        else:
                            default_val = str(default_val).lower() == "true"
                    else:
                        default_val = str(default_val)
                except Exception:
                    default_val = ... if f.required else None
            else:
                default_val = ... if f.required else None

            # Sanitize field name (optional)
            field_name = f.name.strip().replace(" ", "_")
            if not field_name.isidentifier():
                return {"error": f"Invalid field name: {f.name}"}

            field_definitions[field_name] = (py_type, default_val)

        # Dynamically create Pydantic model
        DynamicModel = create_model(req.model_name, **field_definitions)
        try:
            model_schema=DynamicModel.model_json_schema()
            await store_model_in_supabase(model_name,model_schema)
        except Exception as e:
            print("Exception happened:",e)
        # Return confirmation info
        response_fields = {k: str(v[0].__name__) for k, v in field_definitions.items()}
        return {"model_name": req.model_name, "fields": response_fields}
    return RedirectResponse(url="/?msg=Unauthorized+Acess+Denied+Login",status_code=302)
@app.get("/",response_class=HTMLResponse)
async def login_page(request:Request,msg:str=None):
    return templates.TemplateResponse("/login.html",{"request":request,"msg":msg})


@app.post("/login")
async def login_validate(request:Request,username:str=Form(...),password:str=Form(...)):
    print(username,password)
    exist=await admin_exists(username)
    valid=await check_if_admin_valid(username,password) 
    global admin_login
    if exist and valid:
        print("WelcomeAdmin")
        request.session["login"]=True
        return RedirectResponse(url="/ai?msg=Welceome+Admin",status_code=302)
    

@app.get("/ai",response_class=HTMLResponse)
async def ai_page(request:Request,msg:str=None):
    admin_login = request.session.get("login",False)
    if admin_login:
        return templates.TemplateResponse("ai_agent.html",{"request":request,"msg":msg})
    return RedirectResponse(url="/?msg=Unauthorized+Acess+Denied+Login",status_code=302)

@app.post("/ai")
async def ai_page(request:Request,msg:str=None,user_input:str=Form(...)):
    global gemini_api_key
    admin_login = request.session.get("login",False)

    if admin_login:
        data=await get_data_for_gemini()
        instrcuctions="""
                        Instructions:
                        - Analyze the dataset and answer the query accurately.
                        - Return only plain text or list output.
                        - Do not use markdown, bold, or special symbols.
                        - Keep the answer short and direct.
                        """
        gemini_prompt="""You are a data analysis AI.

                        Input:
                        1. Dataset:""" +str(data)+"2. User query:"+user_input+instrcuctions
                        
        ans=await get_gemini_response(gemini_prompt)



        print("AI reply:", ans)
        return JSONResponse({"reply": ans},status_code=200)

    return RedirectResponse(url="/?msg=Unauthorized+Acess+Denied+Login",status_code=302)

@app.get("/about")
async def about_page(request:Request):
    return templates.TemplateResponse("about.html",{"request":request},status_code=200)

@app.post("/logout")
def logout(request:Request):
    #global admin_login
    #admin_login=False
    print("Logout")
    request.session["login"]=False