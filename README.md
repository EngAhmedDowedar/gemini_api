# Gemini API - FastAPI Wrapper 🚀

A powerful FastAPI wrapper that provides OpenAI-compatible chat completion endpoints for Google's Gemini AI. This API allows you to integrate Gemini with any application that expects an OpenAI-style interface.

## ✨ Features

- **OpenAI-Compatible Endpoints**: Use Gemini with any OpenAI API client
- **Chat Completions**: `/v1/chat/completions` endpoint for conversational AI
- **Generic Responses**: `/v1/responses` endpoint for flexible message handling
- **Tool/Function Calling**: Full support for tool calls and function execution
- **Async Browser Automation**: Uses Playwright with headless Chrome to interact with Gemini
- **Message Formatting**: Intelligent prompt building with system instructions, tool context, and conversation history
- **Bearer Token Authentication**: Secure API access with configurable API keys

## 📋 System Requirements

- Python 3.8+
- Chrome/Chromium browser
- 2GB+ RAM (for browser instance)

## 🔧 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/EngAhmedDowedar/gemini_api.git
   cd gemini_api
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn playwright
   playwright install chromium
   ```

## 🚀 Quick Start

1. **Set your API secret key (optional):**
   ```bash
   export API_SECRET_KEY="your-secret-key"
   ```
   If not set, defaults to "Dowedar"

2. **Run the server:**
   ```bash
   python main.py
   ```
   
   The API will be available at `http://localhost:7777`

3. **Test the health endpoint:**
   ```bash
   curl http://localhost:7777/
   ```

## 📡 API Endpoints

### 1. Chat Completions
**Endpoint:** `POST /v1/chat/completions`

**Description:** OpenAI-compatible chat completion endpoint

**Headers:**
```
Authorization: Bearer YOUR_API_SECRET_KEY
Content-Type: application/json
```

**Request Body:**
```json
{
  "model": "gemini-2.0-flash",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "What is the capital of France?"
    }
  ],
  "tools": []
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gemini-2.0-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 12,
    "total_tokens": 57
  }
}
```

### 2. Generic Responses
**Endpoint:** `POST /v1/responses`

**Description:** Flexible endpoint for message processing with optional system instructions

**Headers:**
```
Authorization: Bearer YOUR_API_SECRET_KEY
Content-Type: application/json
```

**Request Body:**
```json
{
  "model": "gemini-2.0-flash",
  "input": "What is 2+2?",
  "instructions": "Be concise and direct.",
  "tools": []
}
```

Or with message array:
```json
{
  "model": "gemini-2.0-flash",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "tools": []
}
```

**Response:**
```json
{
  "id": "resp-abc123...",
  "object": "response",
  "created_at": 1234567890,
  "model": "gemini-2.0-flash",
  "status": "completed",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "2 + 2 = 4"
        }
      ]
    }
  ],
  "usage": {
    "input_tokens": 12,
    "output_tokens": 8,
    "total_tokens": 20
  }
}
```

### 3. List Models
**Endpoint:** `GET /v1/models`

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gemini-2.0-flash",
      "object": "model",
      "owned_by": "mse_ai_api"
    }
  ]
}
```

### 4. Health Check
**Endpoint:** `GET /`

**Response:**
```json
{
  "status": "running",
  "message": "mse_ai_api Server is active!"
}
```

## 🛠️ Tool/Function Calling

The API supports OpenAI-style tool calling. When you provide tools in the request, Gemini will analyze them and respond with tool calls when appropriate.

**Example with tools:**
```json
{
  "model": "gemini-2.0-flash",
  "messages": [
    {
      "role": "user",
      "content": "What's the weather in Cairo?"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get weather information for a location",
        "parameters": {
          "type": "object",
          "properties": {
            "location": {
              "type": "string",
              "description": "City name"
            }
          },
          "required": ["location"]
        }
      }
    }
  ]
}
```

**Response with tool calls:**
```json
{
  "id": "chatcmpl-abc123...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gemini-2.0-flash",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123...",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"location\": \"Cairo\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {
    "prompt_tokens": 80,
    "completion_tokens": 25,
    "total_tokens": 105
  }
}
```

## 🔐 Authentication

All endpoints (except `/` and `/v1/models`) require Bearer token authentication:

```bash
curl -H "Authorization: Bearer YOUR_API_SECRET_KEY" \
  -X POST http://localhost:7777/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'
```

Set the API key via environment variable:
```bash
export API_SECRET_KEY="your-secret-key"
```

## 📁 Project Structure

```
gemini_api/
├── main.py                 # Main FastAPI application
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── .env                   # Environment variables (not included in repo)
```

## 🔄 How It Works

1. **Browser Thread**: On startup, the app launches a headless Chrome browser in a separate async thread
2. **Prompt Formatting**: User messages are intelligently formatted with system instructions and tool definitions
3. **Gemini Interaction**: The formatted prompt is sent to Gemini via browser automation
4. **Response Parsing**: Responses are parsed for tool calls (JSON format) or plain text
5. **OpenAI Compatibility**: Responses are formatted to match OpenAI's chat completion format

## ⚙️ Configuration

### Environment Variables

- `API_SECRET_KEY`: Your API authentication key (default: "Dowedar")

### Browser Options

Modify the browser launch arguments in `AsyncBrowserThread._start_browser()`:
- `--headless`: Run in headless mode (no GUI)
- `--no-sandbox`: Disable sandbox (useful for Docker)
- `--disable-gpu`: Disable GPU acceleration
- `--disable-dev-shm-usage-for-fast-performance`: Better memory usage

## 🐛 Troubleshooting

### Chrome Not Found
```bash
playwright install chromium
```

### Port Already in Use
Change the port in `main.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8000)  # Use different port
```

### Timeout Errors
Increase timeout values in `_talk_to_gemini()` method (values are in milliseconds)

### Browser Hangs
Check if Gemini website has UI changes that break the selectors:
- `[data-placeholder="Ask Gemini"]` - Input field selector
- `message-content` - Response container selector

## 🚀 Deployment

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && \
    playwright install chromium

COPY main.py .

ENV API_SECRET_KEY=your-secret-key
EXPOSE 7777

CMD ["python", "main.py"]
```

### Running with Docker
```bash
docker build -t gemini-api .
docker run -p 7777:7777 -e API_SECRET_KEY=your-key gemini-api
```

## 📝 Integration Examples

### Python + OpenAI Client
```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    base_url="http://localhost:7777/v1"
)

response = client.chat.completions.create(
    model="gemini-2.0-flash",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

### cURL
```bash
curl -X POST http://localhost:7777/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Tell me a joke"}]
  }'
```

## ⚠️ Limitations

- Depends on Gemini web interface (may break with UI changes)
- Rate limited by Google's Gemini service
- Requires active Chrome process (resource intensive)
- No built-in database or persistent storage

## 📄 License

MIT License - feel free to use this project for any purpose

## 👨‍💻 Author

**Eng. Ahmed Dowedar**
- GitHub: [@EngAhmedDowedar](https://github.com/EngAhmedDowedar)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📞 Support

If you encounter any issues:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review the code comments for implementation details
3. Open an issue on GitHub with error logs and reproduction steps

---

**Note**: This project interacts with Google's Gemini through browser automation. Use responsibly and in accordance with Google's Terms of Service.