from fastapi import FastAPI,Request,Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import redis.asyncio as redis 
from gmqtt import Client as mqtt
import os 
from dotenv import load_dotenv,find_dotenv 
import json
import itertools
import httpx
import asyncio
import uuid
from starlette.middleware.sessions import SessionMiddleware

admin_login=False
data_queue_size=10
mqtt_data_queue=asyncio.Queue()

path=find_dotenv()
load_dotenv(path)


mqtt_sub_topic=os.getenv("bridge_server_mqtt_topic")
connection_str=os.getenv("connection_str")
mqtt_port=int(os.getenv("mqtt_port"))


number_of_redis_instances=None
redis_clients={}

async def connected_mqtt(client, flags, rc, properties):
    global mqtt_sub_topic
    print("Connected to Mqtt Broker")
    client.subscribe(mqtt_sub_topic)
    print("Subscribed to topic",mqtt_sub_topic)

async def got_mqtt_message(client, topic, payload, qos, properties):
    global redis_clients,mqtt_data_queue,data_queue_size
    data=payload.decode()
    print("got data from device ",data)
    print()
    print()
    print("Size of Queue is ",mqtt_data_queue.qsize())
    await mqtt_data_queue.put(data)
    if mqtt_data_queue.qsize()>data_queue_size:
        await push_data_to_redis()

async def mqtt_disconnected(client, packet, exc=None):
    print("mqtt broker connection disconnected")

async def push_data_to_redis():
    print(redis_clients)
    redis_names = list(redis_clients.keys())
    print("names found in redis_name",redis_names)
    
    redis_cycle = itertools.cycle(redis_names)
    print(redis_cycle)
    while not mqtt_data_queue.empty():
        data_raw = await mqtt_data_queue.get() 
        data = json.loads(data_raw)
        device_id = data["id"]

        redis_name = next(redis_cycle)
        redis_client = redis_clients[redis_name]

        try:
            await redis_client.set(f"iot-device:{device_id}", json.dumps(data))
            print(f"Stored data for {device_id} in {redis_name}")
        except Exception as e:
            print("Exception happened here:", e)



redis_urls={}
#"buffer1": "redis://default:vnknE2tEz4UDzK7ba3r9Lnp6bKdao8tE@redis-13175.c212.ap-south-1-1.ec2.redns.redis-cloud.com:13175"

@asynccontextmanager
async def slave(app:FastAPI):
    try:
    
        print("slave borned")
        
        global redis_urls
        redis_url_data=await get_urls()
        
        print("This is data from redis_ruls",redis_url_data)
        
        if redis_url_data is not None:
            count=0
            for i in redis_url_data:
                print("Url:",i)
                r_username=i["username"]
                r_password=i["password"]
                r_url=i["url"]
                r_port=i["port"]
                redis_url_format=f"redis://{r_username}:{r_password}@{r_url}:{r_port}"
                redis_urls[f"buffer{count}"]=redis_url_format
                count+=1
        await number_redis_instance_online(redis_urls=redis_urls)

        print()
        mqtt_uid=f"my-client{uuid.uuid4().hex[:6]}"
        mqtt_client=mqtt(mqtt_uid)
        mqtt_client.on_connect = lambda c, f, r, p: asyncio.create_task(connected_mqtt(c, f, r, p))
        mqtt_client.on_message = lambda c, t, p, q, pr: asyncio.create_task(got_mqtt_message(c, t, p, q, pr))
        mqtt_client.on_disconnect = lambda c, p, e=None: asyncio.create_task(mqtt_disconnected(c, p, e))

        await mqtt_client.connect(connection_str,mqtt_port)
        

        
        asyncio.create_task(mqtt_client.connect(connection_str, mqtt_port))
    except Exception as e:
        print("Exception happend when getting urls:",e)
    yield
    print('slave died')


app=FastAPI(lifespan=slave)
app.add_middleware(SessionMiddleware, secret_key=uuid.uuid5(uuid.NAMESPACE_DNS,"HelloWorld"))

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
    
    print("get urls status response:",response.status_code)
    print("response is :",response.json())
    
    if response.status_code in [200,201,204] and response.json()!=[]:
        data=response.json()
        print("Urls found:",data)
        print()
        number_of_redis_instances=len(data)
        return data
    return None


async def redis_instance_health_check(name,url):
    
    print("redis instance hea;th check called")
    
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
   
    print("number of redis instance online called")
    print("number of redis urls:",len(redis_urls))
   
    tasks=[redis_instance_health_check(name,url) for name,url in redis_urls.items() ]
    print("Tasks",tasks)
    results=await asyncio.gather(*tasks)
    clients={name:value for name,value in results if value is not None}
    print("number of redis instance online called its output",clients)
    return len(clients)


def encrypt_password(Password:str)->str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS,Password))
async def add_redis_instance(url:str,port:int,username:str,password:str):
    global supabase_service_key,supabase_admin_table_url
    async with httpx.AsyncClient() as client:
        response= await client.post(
            supabase_redis_table_url,
            headers={
                "apikey": supabase_service_key,
                "Authorization": f"Bearer {supabase_service_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            },
            params={"on_conflict":"url"},
            json={
                "url":url,
                "port":port,
                "username":username,
                "password":password
            }
        )
        if response.text :
            print(response.json())
        return True if response.status_code in [200,201] else False


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
            return False
        print(encrypt_password(Password)==data[0]["Password"])
        if Username==data[0]["Username"] and encrypt_password(Password)==data[0]["Password"]:
            return True  
        return False





    

app.mount("/static",StaticFiles(directory="static"),name="static")
templates=Jinja2Templates(directory="templates")

secret_key_for_login_admin_session=str(uuid.uuid5(uuid.NAMESPACE_DNS,"HelloWorld"))




supabase_admin_table_url=os.getenv("supabase_admin_table_url")
supabase_service_key=os.getenv("supabase_service_key")
supabase_redis_table_url=os.getenv("supabase_redis_table_url")




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
        return len(data)>0
    


@app.get("/",response_class=HTMLResponse)
def loginForm(request:Request,msg:str=None):
    admin_login=request.session.get("login",False)
    if admin_login:
        return RedirectResponse(url="/Dashboard?msg=Welcome+Admin",status_code=302)
    return templates.TemplateResponse("Login.html",{"request":request,"msg":msg})
@app.get("/About",response_class=HTMLResponse)
def aboutpage(request:Request):
    return templates.TemplateResponse("About.html",{"request":request})
@app.get("/Dashboard",response_class=HTMLResponse)
async def dashboardpage(request:Request):
    global supabase_redis_table_url,supabase_service_key,redis_urls,number_of_redis_instances
    admin_login=request.session.get("login",False)
    if admin_login:
        async with httpx.AsyncClient() as client:
            response=await client.get(
                supabase_redis_table_url,
                headers={
                    "apikey": supabase_service_key,
                    "Authorization": f"Bearer {supabase_service_key}"
                }
            )
            print("redis_urls:",redis_urls)
            
            number_redis_instance_active=await number_redis_instance_online(redis_urls=redis_urls)

            
            print("number of active instances",number_redis_instance_active)

        msg=request.query_params.get("msg")
        return templates.TemplateResponse("Dashboard.html",{"request":request,"popup_message":msg,"NumberOfRedisInstance":number_of_redis_instances,"NumberOfActiveRedisInstance":number_redis_instance_active})
    return RedirectResponse("/?msg=Unauthorized+User+Login+First",status_code=302)
@app.post("/RemoveRedisInstance")
async def remove_redis_instance(request:Request,RedisDelUsername:str=Form(...),RedisDelUrl:str=Form(...),RedisDelPort:str=Form(...)):
    print(RedisDelUsername)
    global supabase_redis_table_url,supabase_service_key
    admin_login=request.session.get("login",False)
    if admin_login:
        async with httpx.AsyncClient() as client:
            response =await client.get(
                supabase_redis_table_url,
                headers={
                    "apikey": supabase_service_key,
                    "Authorization": f"Bearer {supabase_service_key}",
                    "Accept": "application/json"
                },
                params={"url":f"eq.{RedisDelUrl}"}
                

            )
            if response.text:    
                data=response.json()
                print('row Found:',data)
            

            
                del_response =await client.delete(
                supabase_redis_table_url,
                headers={
                    "apikey": supabase_service_key,
                    "Authorization": f"Bearer {supabase_service_key}",
                    "Accept": "application/json"
                },
                params={"url":f"eq.{RedisDelUrl}"}
                
            )
            
            print(del_response.status_code)
            if del_response.status_code in [200,201,204] and response.status_code in [200,201] and response.json()!=[]:
                try:
                    del redis_urls[RedisDelUrl]
                    print("delted url",RedisDelUrl)
                    # Delete from in-memory dict

                    

                except Exception as e:
                    print("Exception happedn when deleteing redis url :",e)
                # Also remove from redis_clients
                    for k, client in list(redis_clients.items()):
                        if RedisDelUrl in str(client.connection_pool.connection_kwargs.get("host")):
                            del redis_clients[k]
                            break
                return RedirectResponse(url=f"/Dashboard?msg=Instance+of+url:+{RedisDelUrl}+,+port:+{RedisDelPort}+is+Deleted",status_code=302)
            else :
                return RedirectResponse(url="/RemoveRedisInstance?msg=No Such Records Found",status_code=302)
        
@app.get("/RemoveRedisInstance",response_class=HTMLResponse)
async def remove_redis_instance_form(request:Request):
    msg=request.query_params.get("msg")
    admin_login=request.session.get("login",False)
    
    if (admin_login):
        return templates.TemplateResponse("RemoveRedisInstance.html",{"request":request,"msg":msg})
    return RedirectResponse("/?msg=Unauthorized+User+Login+First",status_code=302) 


@app.post("/AddRedis",response_class=HTMLResponse)
async def add_redis_form(request:Request,RedisUrl:str=Form(...),RedisPort:str=Form(...),RedisUsername:str=Form(...),RedisPassword:str=Form(...)):
    print(f"url:{RedisUrl} , port:{RedisPassword} , username:{RedisUsername} , password:{RedisPassword}")
    msg=f"RedisInstance data Sent to Server"
    admin_login=request.session.get("login",False)
    if admin_login:
        if await add_redis_instance(RedisUrl,int(RedisPort),RedisUsername,RedisPassword):
            name = f"buffer{len(redis_urls)}"
            redis_url_format = f"redis://{RedisUsername}:{RedisPassword}@{RedisUrl}:{RedisPort}"
            redis_urls[RedisUrl] = redis_url_format

            # Connect immediately
            client = redis.from_url(redis_url_format, decode_responses=True)
            try:
                pong = await client.ping()
                if pong:
                    redis_clients[name] = client
                    print(f"Connected to new Redis instance {RedisUrl}")
            except Exception as e:
                print("Failed to connect new Redis instance:", e)
            return RedirectResponse(url="/Dashboard?msg=Instance+Added",status_code=303)
    return RedirectResponse("/?msg=Unauthorized+User+Login+First",status_code=302)

@app.get("/AddRedis",response_class=HTMLResponse)
def addredispage(request:Request):
    admin_login=request.session.get("login",False)
    if (admin_login):
        return templates.TemplateResponse("AddRedisInstance.html",{"request":request})
    return RedirectResponse("/?msg=Unauthorized+User+Login+First",status_code=302)

@app.post("/logout")
def logout(request:Request):
    #global admin_login
    #admin_login=False
    print("Logout")
    request.session["login"]=False

@app.get("/api/latest-data")
async def latest_data():
    global redis_clients
    num=await number_redis_instance_online(redis_urls)

    total_instances = num
    active_instances = 0
    
    for client in redis_clients.values():
        try:
            if await client.ping():
                active_instances += 1
        except:
            continue

    return {
        "NumberOfRedisInstance": total_instances,
        "NumberOfActiveRedisInstance": active_instances
    }


@app.post("/Login")
async def LoginValidate(request:Request,Username:str =Form(...),Password:str= Form(...)):

    exist=await admin_exists(Username)
    valid=await check_if_admin_valid(Username,Password) 
    global admin_login
    if exist and valid:
        print("WelcomeAdmin")
        request.session["login"]=True
        
        return RedirectResponse(url="/Dashboard",status_code=302)
    request.session["login"]=False
    print("Shhuuuuu")
    return RedirectResponse(url="/?msg=Login+Failed",status_code=303)
    