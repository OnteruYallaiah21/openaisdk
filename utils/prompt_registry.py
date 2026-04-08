#======================= START OF System LEVEL IMPORTS =======================
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

prompt_registery_base_path = Path(__file__).resolve().parent.parent 
sys.path.append(str(prompt_registery_base_path))
load_dotenv()

#=======================END OF System LEVEL IMPORTS ==========================

class PromptRegistry:
    """
    A dynamic prompt registry manager for multi-agent systems.
    
    This class handles loading, accessing, and managing prompts from JSON configuration files
    with support for multiple versions, agents, behaviors, and dynamic rules.
    
    Attributes:
        base_path (Path): Base path for the prompt registry
        version (str): Current version of the registry being used
        registry_data (Dict): Loaded JSON data from the registry file
        current_agent (str): Currently selected agent
        current_behavior (str): Currently selected behavior
        
    Example:
        >>> registry = PromptRegistry(version="v1")
        >>> registry.set_agent("technical_agent")
        >>> registry.set_behavior("analytical")
        >>> prompt = registry.build_prompt(user_message="Write code for me")
    """
    
    def __init__(self, version: str = "v1", base_path: Optional[Path] = None):
        """
        Initialize the Prompt Registry with a specific version.
        
        Args:
            version: Version of the registry to load (e.g., "v1", "v2")
            base_path: Custom base path for registry files (uses default if None)
            
        Raises:
            FileNotFoundError: If the registry file doesn't exist
            json.JSONDecodeError: If the JSON file is malformed
        """
        self.version = version
        self.base_path = base_path or prompt_registery_base_path
        self.registry_path = self.base_path / "prompt_registry" / "custom_instructions" / f"{version}.json"
        self.registry_data: Dict[str, Any] = {}
        self.current_agent: Optional[str] = None
        self.current_behavior: Optional[str] = None
        self.conversation_context: List[Dict[str, Any]] = []
        
        # Load the registry on initialization
        self.load_registry()
        
    def load_registry(self) -> Dict[str, Any]:
        """
        Load the prompt registry from JSON file.
        
        Returns:
            Dict containing the loaded registry data
            
        Raises:
            FileNotFoundError: When registry file doesn't exist
            json.JSONDecodeError: When JSON parsing fails
            Exception: For any other unexpected errors
        """
        try:
            logger.info(f"Loading registry from: {self.registry_path}")
            
            if not self.registry_path.exists():
                raise FileNotFoundError(f"Registry file not found at {self.registry_path}")
            
            with open(self.registry_path, 'r', encoding='utf-8') as file:
                self.registry_data = json.load(file)
            
            logger.info(f"✅ Successfully loaded registry version {self.version}")
            logger.info(f"Available keys: {list(self.registry_data.keys())}")
            
            # Set defaults from global config if available
            if 'global_config' in self.registry_data:
                global_config = self.registry_data['global_config']
                self.current_behavior = global_config.get('default_behavior', 'helpful')
            
            # Set default agent if available
            if 'agents' in self.registry_data and self.registry_data['agents']:
                self.current_agent = list(self.registry_data['agents'].keys())[0]
            
            return self.registry_data
            
        except FileNotFoundError as e:
            logger.error(f"❌ File not found: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON format: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error loading registry: {e}")
            raise
    
    def reload_registry(self) -> Dict[str, Any]:
        """
        Reload the registry from disk (useful for dynamic updates).
        
        Returns:
            Dict containing the reloaded registry data
        """
        logger.info("Reloading registry from disk...")
        return self.load_registry()
    
    def get_available_versions(self) -> List[str]:
        """
        Get all available registry versions in the directory.
        
        Returns:
            List of available version names (e.g., ["v1", "v2"])
        """
        try:
            registry_dir = self.base_path / "prompt_registry" / "custom_instructions"
            versions = []
            
            for file_path in registry_dir.glob("*.json"):
                version_name = file_path.stem  # Get filename without extension
                versions.append(version_name)
            
            logger.info(f"Found versions: {versions}")
            return sorted(versions)
            
        except Exception as e:
            logger.error(f"Error getting versions: {e}")
            return []
    
    def switch_version(self, new_version: str) -> Dict[str, Any]:
        """
        Switch to a different version of the registry.
        
        Args:
            new_version: The version to switch to (e.g., "v2")
            
        Returns:
            Dict containing the new registry data
            
        Raises:
            ValueError: If the requested version doesn't exist
        """
        if new_version == self.version:
            logger.info(f"Already using version {new_version}")
            return self.registry_data
        
        available_versions = self.get_available_versions()
        if new_version not in available_versions:
            raise ValueError(f"Version {new_version} not found. Available: {available_versions}")
        
        self.version = new_version
        self.registry_path = self.base_path / "prompt_registry" / "custom_instructions" / f"{new_version}.json"
        return self.load_registry()
    
    def get_all_keys(self) -> Dict[str, List[str]]:
        """
        Get all top-level keys from the registry with their nested keys.
        
        Returns:
            Dictionary mapping top-level keys to their nested keys
        """
        keys_info = {}
        
        for top_key, top_value in self.registry_data.items():
            if isinstance(top_value, dict):
                keys_info[top_key] = list(top_value.keys())
            else:
                keys_info[top_key] = [type(top_value).__name__]
        
        return keys_info
    
    def get_agents(self) -> Dict[str, Any]:
        """
        Get all available agents from the registry.
        
        Returns:
            Dictionary of all agents with their configurations
        """
        return self.registry_data.get('agents', {})
    
    def get_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific agent.
        
        Args:
            agent_name: Name of the agent to retrieve
            
        Returns:
            Agent configuration dictionary
            
        Raises:
            KeyError: If the agent doesn't exist
        """
        agents = self.get_agents()
        if agent_name not in agents:
            available = list(agents.keys())
            raise KeyError(f"Agent '{agent_name}' not found. Available agents: {available}")
        
        return agents[agent_name]
    
    def get_behaviors(self) -> Dict[str, Any]:
        """
        Get all available behaviors from the registry.
        
        Returns:
            Dictionary of all behaviors with their configurations
        """
        return self.registry_data.get('behaviors', {})
    
    def get_behavior(self, behavior_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific behavior.
        
        Args:
            behavior_name: Name of the behavior to retrieve
            
        Returns:
            Behavior configuration dictionary
            
        Raises:
            KeyError: If the behavior doesn't exist
        """
        behaviors = self.get_behaviors()
        if behavior_name not in behaviors:
            available = list(behaviors.keys())
            raise KeyError(f"Behavior '{behavior_name}' not found. Available behaviors: {available}")
        
        return behaviors[behavior_name]
    
    def set_agent(self, agent_name: str) -> None:
        """
        Set the current active agent.
        
        Args:
            agent_name: Name of the agent to activate
            
        Raises:
            KeyError: If the agent doesn't exist
        """
        agent_config = self.get_agent(agent_name)
        self.current_agent = agent_name
        logger.info(f"Switched to agent: {agent_name}")
        
        # Set default behavior if specified for this agent
        if 'default_behavior' in agent_config:
            self.set_behavior(agent_config['default_behavior'])
    
    def set_behavior(self, behavior_name: str) -> None:
        """
        Set the current active behavior.
        
        Args:
            behavior_name: Name of the behavior to activate
            
        Raises:
            KeyError: If the behavior doesn't exist
        """
        self.get_behavior(behavior_name)  # Validate existence
        self.current_behavior = behavior_name
        logger.info(f"Switched to behavior: {behavior_name}")
    
    def get_global_config(self) -> Dict[str, Any]:
        """
        Get global configuration settings.
        
        Returns:
            Dictionary of global configuration
        """
        return self.registry_data.get('global_config', {})
    
    def get_contextual_prompts(self) -> Dict[str, Any]:
        """
        Get contextual prompts for different scenarios.
        
        Returns:
            Dictionary of contextual prompts
        """
        return self.registry_data.get('contextual_prompts', {})
    
    def get_dynamic_rules(self) -> List[Dict[str, Any]]:
        """
        Get dynamic injection rules.
        
        Returns:
            List of dynamic rule configurations
        """
        return self.registry_data.get('dynamic_injection_rules', [])
    
    def build_prompt(self, user_message: str = "", include_context: bool = True) -> tuple[str, float]:
        """
        Build the complete system prompt based on current agent and behavior.
        
        Args:
            user_message: The user's message for context-aware prompting
            include_context: Whether to include conversation context
            
        Returns:
            Tuple of (system_prompt, temperature)
            
        Raises:
            ValueError: If no agent or behavior is set
        """
        if not self.current_agent:
            raise ValueError("No agent selected. Call set_agent() first.")
        
        if not self.current_behavior:
            raise ValueError("No behavior selected. Call set_behavior() first.")
        
        try:
            # Get configurations
            agent_config = self.get_agent(self.current_agent)
            behavior_config = self.get_behavior(self.current_behavior)
            global_config = self.get_global_config()
            
            # Build prompt parts
            prompt_parts = []
            
            # 1. Agent instructions
            if 'instructions' in agent_config:
                prompt_parts.append(agent_config['instructions'])
            
            # 2. Behavior base prompt
            if 'base_prompt' in behavior_config:
                prompt_parts.append(behavior_config['base_prompt'])
            
            # 3. Tone
            if 'tone' in behavior_config:
                prompt_parts.append(f"\nUse a {behavior_config['tone']} tone.")
            
            # 4. Guidelines
            guidelines = behavior_config.get('guidelines', [])
            if guidelines:
                prompt_parts.append("\nGuidelines:")
                for guideline in guidelines:
                    prompt_parts.append(f"- {guideline}")
            
            # 5. Response style
            if 'response_style' in agent_config:
                prompt_parts.append(f"\nResponse style: {agent_config['response_style']}")
            
            # 6. Conversation context
            if include_context and self.conversation_context:
                context_summary = self._get_conversation_summary()
                prompt_parts.append(f"\n{context_summary}")
            
            # 7. Dynamic rules based on user message
            if user_message:
                dynamic_instructions = self._apply_dynamic_rules(user_message)
                if dynamic_instructions:
                    prompt_parts.append(f"\nAdditional: {dynamic_instructions}")
            
            # Get temperature from behavior or global config
            temperature = behavior_config.get('temperature', global_config.get('temperature', 0.7))
            
            full_prompt = "\n".join(prompt_parts)
            logger.info(f"Built prompt for agent '{self.current_agent}' with behavior '{self.current_behavior}'")
            
            return full_prompt, temperature
            
        except Exception as e:
            logger.error(f"Error building prompt: {e}")
            raise
    
    def _apply_dynamic_rules(self, user_message: str) -> str:
        """
        Apply dynamic injection rules based on user message.
        
        Args:
            user_message: The user's message to evaluate
            
        Returns:
            Instructions to add to the prompt
        """
        rules = self.get_dynamic_rules()
        instructions = []
        
        for rule in rules:
            condition = rule.get('condition', '')
            add_instruction = rule.get('add_instruction', '')
            
            try:
                # Simple condition evaluator
                if condition == "user_message.contains('code')" and 'code' in user_message.lower():
                    instructions.append(add_instruction)
                    # Apply behavior change if specified
                    if 'behavior' in rule:
                        self.set_behavior(rule['behavior'])
                
                elif condition == "user_message.length < 10" and len(user_message) < 10:
                    instructions.append(add_instruction)
                    
            except Exception as e:
                logger.warning(f"Error evaluating rule {condition}: {e}")
        
        return " ".join(instructions)
    
    def _get_conversation_summary(self) -> str:
        """
        Get a summary of recent conversation for context.
        
        Returns:
            Formatted conversation summary string
        """
        if not self.conversation_context:
            return ""
        
        summary = "Recent conversation context:\n"
        for msg in self.conversation_context[-5:]:  # Last 5 messages
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:100]  # Truncate long messages
            summary += f"- {role}: {content}\n"
        
        return summary
    
    def add_to_context(self, role: str, content: str) -> None:
        """
        Add a message to conversation context.
        
        Args:
            role: Who said it ("user", "assistant", "system")
            content: The message content
        """
        self.conversation_context.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 20 messages to prevent memory issues
        if len(self.conversation_context) > 20:
            self.conversation_context = self.conversation_context[-20:]
    
    def clear_context(self) -> None:
        """Clear the conversation context."""
        self.conversation_context = []
        logger.info("Conversation context cleared")
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get current registry information.
        
        Returns:
            Dictionary with current configuration info
        """
        return {
            "version": self.version,
            "registry_path": str(self.registry_path),
            "current_agent": self.current_agent,
            "current_behavior": self.current_behavior,
            "available_agents": list(self.get_agents().keys()),
            "available_behaviors": list(self.get_behaviors().keys()),
            "global_config": self.get_global_config(),
            "context_length": len(self.conversation_context)
        }
    
    def validate_registry(self) -> Dict[str, bool]:
        """
        Validate the registry structure and required fields.
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            "has_version": "version" in self.registry_data,
            "has_global_config": "global_config" in self.registry_data,
            "has_behaviors": "behaviors" in self.registry_data and bool(self.registry_data['behaviors']),
            "has_agents": "agents" in self.registry_data and bool(self.registry_data['agents']),
            "is_valid": True
        }
        
        # Validate required fields in behaviors
        if validation['has_behaviors']:
            for behavior_name, behavior_config in self.registry_data['behaviors'].items():
                if 'base_prompt' not in behavior_config:
                    validation['is_valid'] = False
                    validation[f"behavior_{behavior_name}_missing_base_prompt"] = True
        
        # Validate required fields in agents
        if validation['has_agents']:
            for agent_name, agent_config in self.registry_data['agents'].items():
                if 'instructions' not in agent_config:
                    validation['is_valid'] = False
                    validation[f"agent_{agent_name}_missing_instructions"] = True
        
        return validation


class PromptRegistryError(Exception):
    """Custom exception for Prompt Registry errors."""
    pass


#======================= MAIN EXECUTION =======================

def main():
    """
    Main function to demonstrate the PromptRegistry class usage.
    """
    try:
        # Initialize registry with version v1 (or your JSON structure)
        registry = PromptRegistry(version="v1")
        
        print("="*60)
        print("PROMPT REGISTRY DEMONSTRATION")
        print("="*60)
        
        # Get all available keys dynamically
        print("\n📋 ALL AVAILABLE KEYS IN REGISTRY:")
        keys_info = registry.get_all_keys()
        for top_key, nested_keys in keys_info.items():
            print(f"  - {top_key}: {nested_keys}")
        
        # Get registry info
        print("\n📊 REGISTRY INFORMATION:")
        info = registry.get_info()
        for key, value in info.items():
            print(f"  - {key}: {value}")
        
        # Validate registry structure
        print("\n✅ VALIDATION RESULTS:")
        validation = registry.validate_registry()
        for check, result in validation.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}: {result}")
        
        # List available agents
        print("\n🤖 AVAILABLE AGENTS:")
        agents = registry.get_agents()
        for agent_name, agent_config in agents.items():
            print(f"  - {agent_name}: {agent_config.get('description', 'No description')}")
        
        # List available behaviors
        print("\n🎭 AVAILABLE BEHAVIORS:")
        behaviors = registry.get_behaviors()
        for behavior_name, behavior_config in behaviors.items():
            print(f"  - {behavior_name}: {behavior_config.get('tone', 'No tone')}")
        
        # Test with technical agent
        print("\n" + "="*60)
        print("💻 BUILDING PROMPT FOR TECHNICAL AGENT")
        print("="*60)
        
        registry.set_agent("technical_agent")
        registry.set_behavior("analytical")
        
        user_message = "Write a Python function to sort a list"
        system_prompt, temperature = registry.build_prompt(user_message=user_message)
        
        print(f"\nUser: {user_message}")
        print(f"Temperature: {temperature}")
        print(f"\nSystem Prompt:\n{system_prompt}")
        
        # Add to context
        registry.add_to_context("user", user_message)
        
        # Test with support agent
        print("\n" + "="*60)
        print("🎧 BUILDING PROMPT FOR SUPPORT AGENT")
        print("="*60)
        
        registry.set_agent("support_agent")
        registry.set_behavior("helpful")
        
        user_message = "My product is not working"
        system_prompt, temperature = registry.build_prompt(user_message=user_message)
        
        print(f"\nUser: {user_message}")
        print(f"Temperature: {temperature}")
        print(f"\nSystem Prompt:\n{system_prompt}")
        
        # Check available versions
        print("\n" + "="*60)
        print("📁 AVAILABLE VERSIONS")
        print("="*60)
        versions = registry.get_available_versions()
        print(f"Found versions: {versions}")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Make sure the JSON file exists at the specified path")
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.exception("Detailed error traceback:")


if __name__ == "__main__":
    main()