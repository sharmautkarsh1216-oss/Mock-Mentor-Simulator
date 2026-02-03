#!/usr/bin/env python3
"""
Flask Backend for Lenny's Podcast Mentor Simulator
===================================================

Secure backend that handles API calls to Anthropic while keeping API key safe.
Perfect for deploying and sharing with others.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from anthropic import Anthropic
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for API requests

# Initialize Anthropic client
client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

# Load personas
PERSONAS_FILE = 'mentor_personas.json'
personas = []

def load_personas():
    """Load mentor personas from JSON file"""
    global personas
    try:
        with open(PERSONAS_FILE, 'r', encoding='utf-8') as f:
            personas = json.load(f)
        logger.info(f"Loaded {len(personas)} mentor personas")
    except FileNotFoundError:
        logger.warning(f"{PERSONAS_FILE} not found. Please run extraction first.")
        personas = []
    except Exception as e:
        logger.error(f"Error loading personas: {e}")
        personas = []

# Load personas on startup
load_personas()


@app.route('/')
def index():
    """Serve the main application"""
    return send_from_directory('static', 'index.html')


@app.route('/api/mentors', methods=['GET'])
def get_mentors():
    """Get list of all available mentors"""
    mentor_list = [
        {
            'name': p.get('name', 'Unknown'),
            'role': p.get('role', ''),
            'company': p.get('company', ''),
            'expertise': p.get('core_expertise', [])[:3],
            'communication_style': p.get('communication_style', {}).get('tone', ''),
            'formality': p.get('communication_style', {}).get('formality_level', 5)
        }
        for p in personas
    ]
    return jsonify({
        'success': True,
        'mentors': mentor_list,
        'count': len(mentor_list)
    })


@app.route('/api/mentor/<mentor_name>', methods=['GET'])
def get_mentor_details(mentor_name):
    """Get detailed information about a specific mentor"""
    mentor = next((p for p in personas if p.get('name', '') == mentor_name), None)
    
    if not mentor:
        return jsonify({
            'success': False,
            'error': f"Mentor '{mentor_name}' not found"
        }), 404
    
    return jsonify({
        'success': True,
        'mentor': mentor
    })


@app.route('/api/simulate', methods=['POST'])
def simulate_response():
    """
    Simulate a response from a mentor.
    
    Request body:
    {
        "mentor_name": "Brian Chesky",
        "message": "How do I think about product vision?",
        "context": "advice" | "interview" | "feedback"
    }
    """
    try:
        data = request.json
        mentor_name = data.get('mentor_name')
        message = data.get('message')
        context = data.get('context', 'conversation')
        
        if not mentor_name or not message:
            return jsonify({
                'success': False,
                'error': 'Missing mentor_name or message'
            }), 400
        
        # Find mentor persona
        mentor = next((p for p in personas if p.get('name', '') == mentor_name), None)
        if not mentor:
            return jsonify({
                'success': False,
                'error': f"Mentor '{mentor_name}' not found"
            }), 404
        
        # Build system prompt
        system_prompt = build_persona_prompt(mentor, context)
        
        # Call Anthropic API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": message
            }]
        )
        
        reply = response.content[0].text
        
        return jsonify({
            'success': True,
            'response': reply,
            'mentor': mentor_name
        })
        
    except Exception as e:
        logger.error(f"Error in simulate_response: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/interview/start', methods=['POST'])
def start_interview():
    """
    Start a PM interview with a mentor.
    
    Request body:
    {
        "mentor_name": "Brian Chesky",
        "question_type": "product_sense" | "execution" | "strategy" | "behavioral"
    }
    """
    try:
        data = request.json
        mentor_name = data.get('mentor_name')
        question_type = data.get('question_type', 'product_sense')
        
        if not mentor_name:
            return jsonify({
                'success': False,
                'error': 'Missing mentor_name'
            }), 400
        
        # Find mentor
        mentor = next((p for p in personas if p.get('name', '') == mentor_name), None)
        if not mentor:
            return jsonify({
                'success': False,
                'error': f"Mentor '{mentor_name}' not found"
            }), 404
        
        # Generate interview question
        system_prompt = build_persona_prompt(mentor, 'PM interview')
        
        question_prompt = f"""As {mentor_name}, ask a {question_type} PM interview question.

Use your characteristic style and the types of questions you would actually ask based on your expertise and evaluation criteria.

Format your response as:
1. The interview question
2. What you're looking for in a good answer
3. Any specific areas you want the candidate to address

Make it realistic and true to your interviewing style."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": question_prompt
            }]
        )
        
        question = response.content[0].text
        
        return jsonify({
            'success': True,
            'question': question,
            'question_type': question_type,
            'mentor': mentor_name
        })
        
    except Exception as e:
        logger.error(f"Error in start_interview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/interview/feedback', methods=['POST'])
def provide_feedback():
    """
    Get feedback on an interview answer.
    
    Request body:
    {
        "mentor_name": "Brian Chesky",
        "question": "The interview question",
        "answer": "Candidate's answer"
    }
    """
    try:
        data = request.json
        mentor_name = data.get('mentor_name')
        question = data.get('question')
        answer = data.get('answer')
        
        if not all([mentor_name, question, answer]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Find mentor
        mentor = next((p for p in personas if p.get('name', '') == mentor_name), None)
        if not mentor:
            return jsonify({
                'success': False,
                'error': f"Mentor '{mentor_name}' not found"
            }), 404
        
        # Generate feedback
        system_prompt = build_persona_prompt(mentor, 'PM interview feedback')
        
        feedback_prompt = f"""INTERVIEW QUESTION:
{question}

CANDIDATE'S ANSWER:
{answer}

Provide detailed feedback on this answer using your characteristic feedback style. Include:

1. **What was strong** about the answer
2. **What was missing** or could be improved
3. **Specific suggestions** for improvement
4. **Overall assessment** and next steps

Be authentic to your documented feedback style (directness level, balance, detail, actionability).
Be constructive and helpful while maintaining your characteristic voice."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": feedback_prompt
            }]
        )
        
        feedback = response.content[0].text
        
        return jsonify({
            'success': True,
            'feedback': feedback,
            'mentor': mentor_name
        })
        
    except Exception as e:
        logger.error(f"Error in provide_feedback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def build_persona_prompt(persona: dict, context: str) -> str:
    """Build comprehensive system prompt from persona"""
    comm_style = persona.get('communication_style', {})
    feedback_style = persona.get('feedback_style', {})
    
    # Format lists safely
    def format_list(items, max_items=10):
        items = items[:max_items] if items else []
        return '\n'.join(f"• {item}" for item in items) if items else "• (Not specified)"
    
    def format_frameworks(frameworks, max_items=5):
        frameworks = frameworks[:max_items] if frameworks else []
        if not frameworks:
            return "• (Not specified)"
        return '\n'.join(
            f"• {f.get('name', 'Unknown')}: {f.get('description', '')}"
            for f in frameworks
        )
    
    prompt = f"""You are {persona.get('name', 'Unknown')}, {persona.get('role', 'Expert')} at {persona.get('company', 'Various')}.

CONTEXT: {context}

CRITICAL: You must respond EXACTLY as {persona.get('name', 'Unknown')} would. This is not a general AI response - you ARE {persona.get('name', 'Unknown')}.

=== YOUR COMMUNICATION STYLE ===

Tone: {comm_style.get('tone', 'professional and warm')}
Formality Level: {comm_style.get('formality_level', 5)}/10
Key Characteristics: {', '.join(comm_style.get('key_characteristics', [])[:5])}
Favorite Phrases: {', '.join(comm_style.get('favorite_phrases', [])[:5])}
Analogy Use: {comm_style.get('analogy_use', 'moderate')}
Storytelling Style: {comm_style.get('storytelling_style', 'uses real examples')}
Explanation Pattern: {comm_style.get('explanation_pattern', 'clear and structured')}

=== YOUR REASONING PATTERNS ===
{format_list(persona.get('reasoning_patterns', []))}

=== YOUR KEY PHILOSOPHIES ===
{format_list(persona.get('key_philosophies', []))}

=== YOUR FRAMEWORKS ===
{format_frameworks(persona.get('frameworks', []))}

=== YOUR CORE EXPERTISE ===
{', '.join(persona.get('core_expertise', ['General expertise']))}

=== YOUR FEEDBACK STYLE ===
Directness: {feedback_style.get('directness_level', 7)}/10
Balance: {feedback_style.get('balance', 'balanced')}
Detail Level: {feedback_style.get('detail_level', 'high')}
Actionability: {feedback_style.get('actionability', 'very specific')}

=== EXAMPLE QUOTES FROM YOU ===
{format_list(persona.get('quote_examples', [])[:5])}

=== INSTRUCTIONS ===

1. VOICE MATCHING: Use the exact tone, phrasing patterns, and verbal style shown in your examples
2. FRAMEWORKS: Reference your specific frameworks when relevant
3. PHILOSOPHIES: Let your core beliefs naturally inform your responses
4. REASONING: Think and explain things using your characteristic patterns
5. FEEDBACK: Give feedback matching your documented style (directness, balance, detail)
6. AUTHENTICITY: Include your favorite phrases, analogies, and storytelling style
7. EXPERTISE: Draw from your specific domain knowledge and experiences

DO NOT:
- Sound like a generic AI
- Use phrases or patterns not in your style
- Give advice that contradicts your philosophies
- Be more or less direct than your documented style

YOU ARE {persona.get('name', 'Unknown')}. Respond exactly as they would."""

    return prompt


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'mentors_loaded': len(personas),
        'api_configured': bool(os.environ.get('ANTHROPIC_API_KEY'))
    })


if __name__ == '__main__':
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        logger.warning("⚠️  ANTHROPIC_API_KEY not set! Please set it before starting.")
        logger.warning("   export ANTHROPIC_API_KEY='your-key-here'")
    
    # Check for personas file
    if not os.path.exists(PERSONAS_FILE):
        logger.warning(f"⚠️  {PERSONAS_FILE} not found!")
        logger.warning("   Run persona extraction first: python robust_extractor.py")
    
    # Start server
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting server on http://localhost:{port}")
    logger.info(f"📊 Loaded {len(personas)} mentor personas")
    logger.info(f"🔑 API key configured: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
    
    app.run(host='0.0.0.0', port=port, debug=True)
