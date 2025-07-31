#!/usr/bin/env python3
"""
Example demonstrating conversation logging functionality.

This example shows how to use the conversation logging system
to track calls, conversations, and messages.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up test environment variables to bypass validation
os.environ.update({
    'ENVIRONMENT': 'development',
    'SECRET_KEY': 'test-secret-key-for-example-purposes-only',
    'LIVEKIT_API_KEY': 'APItest1234567890abcdef',  # Proper LiveKit format
    'LIVEKIT_API_SECRET': 'test-api-secret-for-example-purposes-only-long-enough',
    'DEEPGRAM_API_KEY': '1234567890abcdef1234567890abcdef12345678',  # Proper Deepgram format (32+ chars hex)
    'OPENAI_API_KEY': 'sk-test1234567890abcdef1234567890abcdef1234567890abcdef',  # Proper OpenAI format
    'CARTESIA_API_KEY': 'sk_car_test1234567890abcdef1234567890abcdef',  # Proper Cartesia format
    'DATABASE_URL': 'sqlite:///./data/example_voice_ai.db',
    'DEBUG': 'true'
})

from src.database.connection import init_database, cleanup_database
from src.database.logging_integration import get_conversation_logger
from src.config import get_settings


async def demonstrate_conversation_logging():
    """Demonstrate the conversation logging system."""
    print("🎯 Voice AI Agent - Conversation Logging Example")
    print("=" * 60)
    
    # Initialize database
    print("🗄️  Initializing database...")
    try:
        db_manager = await init_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return
    
    # Get conversation logger
    logger = get_conversation_logger()
    
    try:
        # Example 1: Start a call
        print("\n📞 Example 1: Starting a call")
        call_id = "call_example_001"
        caller_number = "+1234567890"
        
        success = await logger.start_call(
            call_id=call_id,
            caller_number=caller_number,
            livekit_room="room_001",
            metadata={"source": "example", "test": True}
        )
        
        if success:
            print(f"✅ Call started: {call_id}")
        else:
            print(f"❌ Failed to start call: {call_id}")
            return
        
        # Example 2: Start a conversation
        print("\n💬 Example 2: Starting a conversation")
        conversation_id = await logger.start_conversation(
            call_id=call_id,
            ai_model="gpt-4",
            system_prompt="You are a helpful voice assistant."
        )
        
        if conversation_id:
            print(f"✅ Conversation started: {conversation_id}")
        else:
            print("❌ Failed to start conversation")
            return
        
        # Example 3: Log user message
        print("\n👤 Example 3: Logging user message")
        user_success = await logger.log_user_message(
            conversation_id=conversation_id,
            content="Hello, can you help me with my account?",
            audio_duration=2.5,
            stt_confidence=0.95,
            stt_language="en-US",
            processing_time_ms=150.0,
            alternatives=["Hello, can you help me with my account?", "Hello, can you help me with my count?"]
        )
        
        if user_success:
            print("✅ User message logged")
        else:
            print("❌ Failed to log user message")
        
        # Example 4: Log assistant message
        print("\n🤖 Example 4: Logging assistant message")
        assistant_success = await logger.log_assistant_message(
            conversation_id=conversation_id,
            content="Of course! I'd be happy to help you with your account. What specific information do you need?",
            processing_time_ms=1200.0,
            llm_model="gpt-4",
            llm_tokens_input=25,
            llm_tokens_output=18,
            llm_cost_usd=0.0012,
            tts_voice_id="voice_001",
            tts_audio_duration=4.2,
            tts_cost_usd=0.0008
        )
        
        if assistant_success:
            print("✅ Assistant message logged")
        else:
            print("❌ Failed to log assistant message")
        
        # Example 5: Log more conversation turns
        print("\n🔄 Example 5: Logging multiple conversation turns")
        
        # User turn 2
        await logger.log_user_message(
            conversation_id=conversation_id,
            content="I need to check my balance",
            audio_duration=1.8,
            stt_confidence=0.92,
            processing_time_ms=120.0
        )
        
        # Assistant turn 2
        await logger.log_assistant_message(
            conversation_id=conversation_id,
            content="I can help you check your balance. Let me look that up for you.",
            processing_time_ms=980.0,
            llm_model="gpt-4",
            llm_tokens_input=45,
            llm_tokens_output=15,
            llm_cost_usd=0.0015,
            tts_voice_id="voice_001",
            tts_audio_duration=3.1,
            tts_cost_usd=0.0006
        )
        
        # User turn 3
        await logger.log_user_message(
            conversation_id=conversation_id,
            content="Thank you",
            audio_duration=0.8,
            stt_confidence=0.98,
            processing_time_ms=80.0
        )
        
        # Assistant turn 3
        await logger.log_assistant_message(
            conversation_id=conversation_id,
            content="You're welcome! Your current balance is $1,234.56. Is there anything else I can help you with?",
            processing_time_ms=1100.0,
            llm_model="gpt-4",
            llm_tokens_input=60,
            llm_tokens_output=22,
            llm_cost_usd=0.0018,
            tts_voice_id="voice_001",
            tts_audio_duration=5.5,
            tts_cost_usd=0.0010
        )
        
        print("✅ Multiple conversation turns logged")
        
        # Example 6: Log system event
        print("\n📋 Example 6: Logging system event")
        event_success = await logger.log_event(
            event_type="balance_lookup",
            severity="INFO",
            message="User requested balance lookup",
            component="account_service",
            call_id=call_id,
            conversation_id=conversation_id,
            metadata={"account_type": "checking", "lookup_time_ms": 45}
        )
        
        if event_success:
            print("✅ System event logged")
        else:
            print("❌ Failed to log system event")
        
        # Example 7: Get conversation history
        print("\n📜 Example 7: Retrieving conversation history")
        history = await logger.get_conversation_history(conversation_id)
        
        print(f"📊 Conversation history ({len(history)} messages):")
        for i, msg in enumerate(history, 1):
            role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️"}.get(msg["role"], "❓")
            print(f"  {i}. {role_emoji} {msg['role'].title()}: {msg['content'][:50]}...")
            if msg.get('processing_duration_ms'):
                print(f"     ⏱️  Processing time: {msg['processing_duration_ms']:.1f}ms")
            if msg.get('stt_confidence'):
                print(f"     🎯 STT confidence: {msg['stt_confidence']:.2f}")
            if msg.get('llm_tokens_input'):
                print(f"     🧠 LLM tokens: {msg['llm_tokens_input']} in, {msg['llm_tokens_output']} out")
        
        # Example 8: End conversation
        print("\n🏁 Example 8: Ending conversation")
        conv_end_success = await logger.end_conversation(
            conversation_id=conversation_id,
            summary="User inquired about account balance. Balance provided successfully.",
            topic="account_balance"
        )
        
        if conv_end_success:
            print("✅ Conversation ended and metrics updated")
        else:
            print("❌ Failed to end conversation")
        
        # Example 9: End call
        print("\n📴 Example 9: Ending call")
        call_end_success = await logger.end_call(call_id)
        
        if call_end_success:
            print("✅ Call ended")
        else:
            print("❌ Failed to end call")
        
        # Example 10: Get call statistics
        print("\n📊 Example 10: Getting call statistics")
        stats = await logger.get_call_statistics(hours=24)
        
        if "error" not in stats:
            print("📈 Call Statistics (last 24 hours):")
            print(f"  📞 Total calls: {stats['calls']['total']}")
            print(f"  ✅ Completed calls: {stats['calls']['completed']}")
            print(f"  🎯 Success rate: {stats['calls']['success_rate']:.1f}%")
            print(f"  ⏱️  Average duration: {stats['calls']['avg_duration_seconds']:.1f}s")
            print(f"  💰 Total cost: ${stats['performance']['total_cost_usd']:.4f}")
            print(f"  ⚡ Average response time: {stats['performance']['avg_response_time_ms']:.1f}ms")
            print(f"  📝 Total messages: {stats['performance']['total_messages']}")
        else:
            print(f"❌ Failed to get statistics: {stats['error']}")
        
        print("\n🎉 Conversation logging example completed successfully!")
        
    except Exception as e:
        print(f"💥 Error during example: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await cleanup_database()
        print("✅ Cleanup complete")


async def demonstrate_error_handling():
    """Demonstrate error handling in conversation logging."""
    print("\n🚨 Error Handling Examples")
    print("-" * 40)
    
    # Initialize database
    db_manager = await init_database()
    logger = get_conversation_logger()
    
    try:
        # Example 1: Try to start conversation for non-existent call
        print("\n❌ Example 1: Starting conversation for non-existent call")
        conversation_id = await logger.start_conversation(
            call_id="non_existent_call",
            ai_model="gpt-4"
        )
        
        if conversation_id is None:
            print("✅ Correctly handled non-existent call")
        else:
            print("❌ Should have failed for non-existent call")
        
        # Example 2: Try to log message for non-existent conversation
        print("\n❌ Example 2: Logging message for non-existent conversation")
        success = await logger.log_user_message(
            conversation_id="non_existent_conversation",
            content="This should fail"
        )
        
        if not success:
            print("✅ Correctly handled non-existent conversation")
        else:
            print("❌ Should have failed for non-existent conversation")
        
        # Example 3: Try to end non-existent call
        print("\n❌ Example 3: Ending non-existent call")
        success = await logger.end_call("non_existent_call")
        
        if not success:
            print("✅ Correctly handled non-existent call ending")
        else:
            print("❌ Should have failed for non-existent call")
        
        print("\n✅ Error handling examples completed")
        
    except Exception as e:
        print(f"💥 Unexpected error in error handling examples: {e}")
    
    finally:
        await cleanup_database()


async def main():
    """Main function to run all examples."""
    print("🎯 Voice AI Agent - Conversation Logging Examples")
    print("=" * 60)
    
    # Check if database is configured
    settings = get_settings()
    print(f"📋 Using database: {settings.database_url}")
    
    # Run main demonstration
    await demonstrate_conversation_logging()
    
    # Run error handling demonstration
    await demonstrate_error_handling()
    
    print("\n🎉 All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())