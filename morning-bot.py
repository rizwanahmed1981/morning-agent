import chainlit as cl
from typing import Dict, List, TypedDict, Optional
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
from duckduckgo_search import DDGS

# Load environment variables
load_dotenv()

# Type definitions
class Message(TypedDict):
    role: str
    content: str
    timestamp: str

class UserData(TypedDict):
    current_habits: List[str]
    energizing_activities: List[str]
    goals: List[str]
    conversation_history: List[Message]

# Configure Gemini
try:
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    print(f"Error configuring Gemini: {str(e)}")
    raise

# Initialize DuckDuckGo search
ddgs = DDGS()

async def search_web(query: str, max_results: int = 3) -> List[Dict]:
    """Perform web search and return results."""
    try:
        results = []
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                'title': r['title'],
                'link': r['link'],
                'snippet': r['body']
            })
        return results
    except Exception as e:
        print(f"Search error: {str(e)}")
        return []

async def search_youtube(query: str, max_results: int = 3) -> List[Dict]:
    """Search YouTube videos and return results."""
    try:
        print(f"Starting YouTube search for: {query}")  # Debug log
        results = []
        search_results = list(ddgs.videos(query, max_results=max_results))
        print(f"Found {len(search_results)} results")  # Debug log
        
        for r in search_results:
            try:
                result = {
                    'title': r.get('title', 'No title'),
                    'link': r.get('link', 'No link'),
                    'duration': r.get('duration', 'N/A'),
                    'channel': r.get('channel', 'N/A')
                }
                print(f"Processed result: {result['title']}")  # Debug log
                results.append(result)
            except Exception as e:
                print(f"Error processing result: {str(e)}")  # Debug log
                continue
                
        return results
    except Exception as e:
        print(f"YouTube search error: {str(e)}")  # Debug log
        print(f"Error type: {type(e)}")  # Debug log
        return []

# Store user preferences and responses
user_data: UserData = {
    "current_habits": [],
    "energizing_activities": [],
    "goals": [],
    "conversation_history": []
}

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Morning routine ideation",
            message="Can you help me create a personalized morning routine that would help increase my productivity throughout the day? Start by asking me about my current habits and what activities energize me in the morning.",
            icon="/public/idea.svg",
            ),
        cl.Starter(
            label="Search YouTube",
            message="Find me a motivational morning routine video on YouTube.",
            icon="/public/video.svg",
            ),
        cl.Starter(
            label="Search Web",
            message="Find me some morning routine tips and articles.",
            icon="/public/search.svg",
            )
        ]

@cl.on_chat_start
async def on_chat_start():
    await cl.Message(content="Hello! I'm your morning routine assistant powered by Gemini AI. I can help you create a morning routine, search for videos, and find helpful articles. How can I help you today?").send()

async def get_gemini_response(prompt: str, context: str = "") -> str:
    """Get response from Gemini model with context."""
    try:
        # Prepare the full prompt with context
        full_prompt = f"{context}\n\nUser: {prompt}\nAssistant:"
        
        # Generate response with safety settings
        response = await model.generate_content_async(
            full_prompt,
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        )
        return response.text
    except Exception as e:
        error_message = f"I apologize, but I encountered an error: {str(e)}"
        print(f"Gemini API Error: {str(e)}")  # Log the error for debugging
        return error_message

def add_to_conversation_history(message: str, role: str = "user") -> None:
    """Add a message to the conversation history with proper typing."""
    user_data["conversation_history"].append(Message(
        role=role,
        content=message,
        timestamp=datetime.now().isoformat()
    ))

@cl.on_message
async def on_message(message: cl.Message):
    content = message.content.lower()
    
    # Add message to conversation history
    add_to_conversation_history(message.content)
    
    try:
        # Handle YouTube search requests
        if any(keyword in content for keyword in ["youtube", "video", "watch"]):
            search_query = content
            for keyword in ["youtube", "video", "watch", "find", "search"]:
                search_query = search_query.replace(keyword, "").strip()
            
            if not search_query:
                search_query = "morning routine motivation"
            
            print(f"Processing YouTube search request: {search_query}")  # Debug log
            results = await search_youtube(search_query)
            print(f"Search returned {len(results)} results")  # Debug log
            
            if results:
                response = "Here are some relevant videos:\n\n"
                for result in results:
                    response += f"📺 {result['title']}\n"
                    response += f"🔗 {result['link']}\n"
                    response += f"⏱️ Duration: {result['duration']}\n"
                    response += f"👤 Channel: {result['channel']}\n\n"
            else:
                response = "I couldn't find any relevant videos. Let me try a different search approach..."
                # Try a more generic search if specific search fails
                fallback_query = "morning routine motivation"
                print(f"Trying fallback search: {fallback_query}")  # Debug log
                fallback_results = await search_youtube(fallback_query)
                
                if fallback_results:
                    response = "Here are some motivational morning routine videos:\n\n"
                    for result in fallback_results:
                        response += f"📺 {result['title']}\n"
                        response += f"🔗 {result['link']}\n"
                        response += f"⏱️ Duration: {result['duration']}\n"
                        response += f"👤 Channel: {result['channel']}\n\n"
                else:
                    response = "I apologize, but I'm having trouble finding videos right now. Would you like to try a different type of search or continue with creating a morning routine?"
            
            add_to_conversation_history(response, "assistant")
            await cl.Message(content=response).send()
            return

        # Handle web search requests
        if any(keyword in content for keyword in ["search", "find", "look for"]):
            search_query = content
            for keyword in ["search", "find", "look for"]:
                search_query = search_query.replace(keyword, "").strip()
            
            if not search_query:
                search_query = "morning routine tips"
            
            print(f"Searching web for: {search_query}")  # Debug log
            results = await search_web(search_query)
            
            if results:
                response = "Here are some relevant resources:\n\n"
                for result in results:
                    response += f"📚 {result['title']}\n"
                    response += f"🔗 {result['link']}\n"
                    response += f"📝 {result['snippet'][:200]}...\n\n"
            else:
                response = "I couldn't find any relevant results. Would you like to try a different search query?"
            
            add_to_conversation_history(response, "assistant")
            await cl.Message(content=response).send()
            return

        # Original morning routine logic
        if "help me create a personalized morning routine" in content:
            response = await get_gemini_response(
                "Start a conversation about creating a morning routine. Ask about current habits.",
                "You are a morning routine expert. Start by asking about the user's current morning habits."
            )
            add_to_conversation_history(response, "assistant")
            await cl.Message(content=response).send()
            return
        
        # If we're collecting current habits
        if not user_data["current_habits"]:
            user_data["current_habits"] = [habit.strip() for habit in content.split(",")]
            response = await get_gemini_response(
                "Ask about energizing morning activities",
                f"User's current habits: {', '.join(user_data['current_habits'])}"
            )
            add_to_conversation_history(response, "assistant")
            await cl.Message(content=response).send()
            return
        
        # If we're collecting energizing activities
        if not user_data["energizing_activities"]:
            user_data["energizing_activities"] = [activity.strip() for activity in content.split(",")]
            response = await get_gemini_response(
                "Ask about morning goals",
                f"User's current habits: {', '.join(user_data['current_habits'])}\nEnergizing activities: {', '.join(user_data['energizing_activities'])}"
            )
            add_to_conversation_history(response, "assistant")
            await cl.Message(content=response).send()
            return
        
        # If we're collecting goals
        if not user_data["goals"]:
            user_data["goals"] = [goal.strip() for goal in content.split(",")]
            
            # Generate personalized morning routine using Gemini
            context = f"""
            User's current habits: {', '.join(user_data['current_habits'])}
            Energizing activities: {', '.join(user_data['energizing_activities'])}
            Goals: {', '.join(user_data['goals'])}
            
            Create a detailed, personalized morning routine that incorporates these elements.
            Include specific timing suggestions and explain the benefits of each activity.
            """
            
            routine = await get_gemini_response("Generate a morning routine", context)
            add_to_conversation_history(routine, "assistant")
            await cl.Message(content=routine).send()
            
            follow_up = await get_gemini_response(
                "Ask if they want to make any adjustments or need explanations",
                "You've just provided a morning routine. Ask if they want to make adjustments or need explanations."
            )
            add_to_conversation_history(follow_up, "assistant")
            await cl.Message(content=follow_up).send()
            return
        
        # Handle follow-up questions using Gemini
        context = f"""
        User's preferences:
        - Current habits: {', '.join(user_data['current_habits'])}
        - Energizing activities: {', '.join(user_data['energizing_activities'])}
        - Goals: {', '.join(user_data['goals'])}
        
        Previous conversation: {str(user_data['conversation_history'][-5:])}
        """
        
        response = await get_gemini_response(message.content, context)
        add_to_conversation_history(response, "assistant")
        await cl.Message(content=response).send()
        
    except Exception as e:
        error_message = f"I apologize, but I encountered an error: {str(e)}"
        print(f"Error in message handling: {str(e)}")  # Log the error for debugging
        await cl.Message(content=error_message).send()

def generate_morning_routine(user_data: UserData) -> str:
    """Generate a personalized morning routine based on user preferences."""
    routine = "🌅 Your Personalized Morning Routine:\n\n"
    
    # Add energizing activities first
    if user_data["energizing_activities"]:
        routine += "1. Start with energizing activities:\n"
        for activity in user_data["energizing_activities"]:
            routine += f"   - {activity.strip()}\n"
    
    # Incorporate current habits
    if user_data["current_habits"]:
        routine += "\n2. Maintain your current habits:\n"
        for habit in user_data["current_habits"]:
            routine += f"   - {habit.strip()}\n"
    
    # Add goal-oriented activities
    if user_data["goals"]:
        routine += "\n3. Goal-focused activities:\n"
        for goal in user_data["goals"]:
            routine += f"   - {goal.strip()}\n"
    
    routine += "\n💡 Tips:\n"
    routine += "- Wake up at the same time every day\n"
    routine += "- Start with a glass of water\n"
    routine += "- Take small steps to build consistency\n"
    
    return routine