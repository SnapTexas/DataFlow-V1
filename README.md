# DataFlow-V1
🧩 Real-Time IoT Data Pipeline
📖 Overview

This project implements a modular real-time data pipeline designed to efficiently process continuous IoT sensor streams — from ingestion to intelligent analysis.
It ensures scalability, fault tolerance, and near real-time responsiveness using lightweight and asynchronous technologies.

⚙️ Architecture
IoT Devices → MQTT Broker → Bridge Server → Redis Buffer 
             → Validation Server → Database → AI Agent → Dashboard

🔹 Layer Description
Layer	Description
IoT Device	Collects sensor data (e.g., temperature, humidity, distance).
MQTT Broker	Handles asynchronous message transfer between IoT devices and backend.
Bridge Server	Connects MQTT to Redis, performs load balancing (round-robin), and manages authentication.
Redis Buffer	Acts as a high-speed in-memory queue for data ingestion.
Validation Server	Validates and structures incoming data dynamically using FastAPI.
Database (SQL)	Stores validated and processed data for analysis and visualization.
AI Agent	Processes historical data for insights and summarization.
Dashboard	Displays data trends and AI-generated insights in real time.
🧠 Key Features

⚡ Real-time Data Handling — Streams IoT data seamlessly through MQTT and Redis.

🧩 Modular Design — Each layer runs independently, enabling scalability.

🔐 Admin Authentication — Secure login for admin panels in Bridge & Validation servers.

🔁 Load Balancing — Redis instances managed using round-robin distribution.

🧱 Dynamic Data Models — Validation server supports dynamically generated models.

🧮 AI Integration — AI agent performs intelligent data summarization and anomaly detection.

📊 Web Dashboard — Displays sensor history, live updates, and summarized insights.

🏗️ System Architecture Diagram

(If you have a data flow diagram image, include it here)
Example:

[IoT Sensor] → [MQTT Broker] → [BridgeServer] → [Redis Buffer] → [Validation Server] → [SQL Database] → [AI Agent] → [Dashboard]

🧰 Technologies Used
Component	Technology
IoT Communication	MQTT
API & Backend	FastAPI
Data Buffer	Redis
Database	MySQL / Supabase
Frontend / Dashboard	HTML, JS, Chart.js
AI & Analysis	Python (NumPy / Pandas / Custom AI Logic)
Authentication	JWT / Encrypted Admin Passwords
🚀 Installation & Setup
1️⃣ Clone Repository
git clone https://github.com/yourusername/data-pipeline.git
cd data-pipeline

2️⃣ Setup Environment

Create a .env file:

MQTT_BROKER_URL=your_mqtt_broker_url
REDIS_HOST=localhost
REDIS_PORT=6379
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Run Services
# Start Bridge Server
uvicorn bridge_server:app --reload --port 8001

# Start Validation Server
uvicorn validation_server:app --reload --port 8002

5️⃣ Start MQTT and Redis

Ensure your MQTT Broker and Redis Server are running locally or remotely.

🧾 Example Data Flow

Incoming Sensor Data (from NodeMCU / ESP8266):

{
  "device_id": "sensor_001",
  "temperature": 29.5,
  "humidity": 62,
  "timestamp": "2025-10-13T10:45:00"
}


Bridge Server → Redis → Validation Server → Database

🧩 API Endpoints (Example)
Method	Endpoint	Description
POST	/mqtt/publish	Publish data to MQTT broker
POST	/bridge/ingest	Bridge server accepts IoT data
GET	/validate	View validated entries
POST	/admin/login	Admin login
GET	/ai/summary	Retrieve AI insights
🧠 AI Agent Summary Example

Input: Last 24-hour sensor data
Output:

“Average temperature remained stable at 28.7°C with minor fluctuations between 27°C and 30°C. Humidity increased slightly post 6 PM.”

🔒 Security

Encrypted admin credentials (hashed passwords)

restricted routes

Secure environment variables for keys and endpoints

Limitations

Despite successfully implementing a functional real-time IoT data pipeline, the 
current system has several limitations: 
1. Single Instance Architecture 
o Both the Bridge Server and Data Validation Server currently run as single 
instances. 
o This creates potential bottlenecks and a single point of failure. 
2. Limited Fault Tolerance 
o Redis buffering ensures some smoothing, but if a Redis instance goes down, 
recovery and failover are limited. 
3. Scope of Data Sources 
o Currently, the pipeline only processes IoT sensor data. 
o Integration of other types of structured or unstructured data is not supported 
yet. 

4. AI Agent Capabilities 
o The AI agent only provides insights and answers based on stored data. 
o It does not autonomously act on data or trigger tasks in the system. 
5. Security Constraints 
o Data transmission between IoT devices, MQTT broker, and servers lacks end
to-end encryption. 
o Authentication and authorization mechanisms are limited to admin login for 
dashboards. 
6. Dynamic Scaling 
o While Redis instances can be added or removed dynamically, the servers 
themselves cannot scale horizontally. 
7. Real-Time Metrics & Monitoring 
o The system does not provide advanced metrics or monitoring dashboards for 
performance, latency, or data health. 

📊 Future Enhancements


While the current implementation of the IoT data pipeline (v1) demonstrates a functional 
end-to-end system, several improvements can be planned for the next version (v2) to enhance 
scalability, intelligence, and flexibility: 
 Multi-Instance Fault Tolerance: 
o Deploy multiple instances of Bridge and Data Validation servers. 
o Implement leader election among instances to coordinate workload, avoid 
conflicts, and provide seamless failover. 
o Ensure high availability even if some instances fail. 
 Dynamic Multi-Model Validation: 
o Allow users to create and manage multiple data models simultaneously. 
o Enable validation of diverse data types beyond IoT, such as environmental, 
industrial, or financial datasets. 
o Support real-time integration of new data types without interrupting pipeline 
operations. 
 Proactive AI Agent: 
o Extend the AI agent to not only provide insights but also act on data 
automatically. 
o Example actions could include generating alerts, triggering notifications, 
adjusting IoT device parameters, or automating routine decisions based on 
detected patterns. 
o Allow AI to combine multiple data sources to make more informed decisions, 
such as integrating weather, location, or sensorless data with IoT readings. 
 Enhanced Security: 
o Implement end-to-end encryption for all data flows between devices, servers, 
Redis instances, and database. 
o Enforce strict authentication and authorization for both users and system 
components. 
 System Monitoring and Metrics: 

 
   
 
o Track performance metrics at each pipeline layer, including queue backlogs, 
Redis utilization, and server latency. 
o Use metrics to enable automatic scaling of servers or Redis nodes when 
thresholds are crossed. 
 Cloud-Optimized Deployment: 
o Adapt the pipeline for containerized deployment on cloud platforms using 
orchestration tools like Kubernetes. 
o Ensure low-latency, globally available services with automatic scaling and 
fault tolerance. 
 Multi-Source Data Integration: 
o Expand the pipeline to handle multiple types of data sources concurrently, not 
just IoT. 
o Enable the AI agent to analyze and correlate data from diverse sources for 
richer insights and automated decision-making. 

👨‍💻 Author

Snap
B.Tech Computer Science | IoT & AI Enthusiast
📧 Email: [your email here]
🔗 GitHub: [your GitHub link here]
