# agents/conversation/agent.py
from core.schemas import AgentDecision
from typing import Dict, Any

class ConversationAgent:
    """Decides what to say based on context"""
    
    def __init__(self):
        self.llm = LLMEngine()  # Use LLM engine, not direct OpenAI
        self.memory = MemoryEngine()
        self.config = load_config("agents/conversation/config.yaml")
    
    async def decide(self, context: Dict[str, Any]) -> AgentDecision:
        """
        Given context (user message, history, etc.), decide:
        - What to say
        - What actions to take
        - Confidence level
        - Reasoning
        """
        # 1. Retrieve relevant memory
        memories = await self.memory.retrieve(context["user_message"])
        
        # 2. Build prompt with system prompt + context + memory
        system_prompt = open("agents/conversation/prompts.py").read()
        user_prompt = f"""
        User message: {context['user_message']}
        Context: {context['context']}
        Recent memory: {memories}
        """
        
        # 3. Call LLM via engine
        response = await self.llm.reason(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tools=self._get_tools(),
        )
        
        # 4. Parse structured response
        decision = AgentDecision(
            agent_name="conversation",
            reasoning=response.reasoning,
            next_action=response.action,
            confidence=response.confidence,
        )
        
        # 5. Log decision for analysis
        await self.memory.log_decision(decision)
        
        return decision
    
    def _get_tools(self) -> List[Tool]:
        """Tools this agent can use"""
        return [
            Tool(name="retrieve_calendar", ...),
            Tool(name="retrieve_memory", ...),
            Tool(name="check_weather", ...),
        ]
    
    async def handle_feedback(self, result: AgentResult):
        """Learn from outcomes (for future improvements)"""
        # Log what happened
        # Update agent metrics
        # Fine-tune prompts if needed
        pass