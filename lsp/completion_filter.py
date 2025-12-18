import logging
import re
from difflib import SequenceMatcher

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class CompletionFilter:
    """Filter and sort completions based on context and relevance."""
    
    # LSP completion kinds
    KIND_TEXT = 1
    KIND_METHOD = 2
    KIND_FUNCTION = 3
    KIND_CONSTRUCTOR = 4
    KIND_FIELD = 5
    KIND_VARIABLE = 6
    KIND_CLASS = 7
    KIND_INTERFACE = 8
    KIND_MODULE = 9
    KIND_PROPERTY = 10
    KIND_UNIT = 11
    KIND_VALUE = 12
    KIND_ENUM = 13
    KIND_KEYWORD = 14
    KIND_SNIPPET = 15
    
    @staticmethod
    def get_context(text_before_cursor: str) -> dict:
        """Analyze the context before the cursor."""
        context = {
            'is_import': False,
            'is_after_dot': False,
            'is_blank_line': False,
            'partial_word': '',
            'indent_level': 0,
            'after_keyword': None
        }
        
        # Check if line is blank or just whitespace
        if not text_before_cursor.strip():
            context['is_blank_line'] = True
            context['indent_level'] = len(text_before_cursor) - len(text_before_cursor.lstrip())
            return context
        
        # Check for import statement
        if re.search(r'\bimport\s+\w*$', text_before_cursor) or \
           re.search(r'\bfrom\s+\w+\s+import\s+\w*$', text_before_cursor):
            context['is_import'] = True
        
        # Check if after a dot (accessing attribute/method)
        if re.search(r'\.\w*$', text_before_cursor):
            context['is_after_dot'] = True
        
        # Extract partial word being typed
        match = re.search(r'(\w+)$', text_before_cursor)
        if match:
            context['partial_word'] = match.group(1)
        
        # Check for keywords before cursor
        keywords = ['def', 'class', 'if', 'for', 'while', 'with', 'try', 'except']
        for keyword in keywords:
            if re.search(rf'\b{keyword}\s+\w*$', text_before_cursor):
                context['after_keyword'] = keyword
                break
        
        context['indent_level'] = len(text_before_cursor) - len(text_before_cursor.lstrip())
        
        return context
    
    @staticmethod
    def calculate_relevance_score(completion: dict, context: dict) -> float:
        """Calculate a relevance score for a completion based on context."""
        label = completion.get('label', '')
        kind = completion.get('kind', 0)
        sort_text = completion.get('sortText', '')
        partial = context['partial_word']
        
        score = 0.0
        
        # CRITICAL: Penalize underscore items FIRST, before any bonuses
        # This prevents _PathT from beating Path
        if label.startswith('_') and not partial.startswith('_'):
            score -= 500  # Massive penalty for underscore
            # Double underscore (dunder) is even worse
            if label.startswith('__'):
                score -= 500  # Total -1000 for dunder
        
        # Exact prefix match (case-sensitive) is THE most important
        if label.startswith(partial) and partial:
            score += 200
            # Exact case match is even better
            if label[:len(partial)] == partial:
                score += 100
            
            # HUGE bonus if the match is at the START and complete word boundary
            # e.g., "Path" starting with "Pa" is way better than "_PathT" containing "Pa"
            if label[0] == partial[0]:  # First character matches
                score += 150
        
        # Case-insensitive prefix match (less important)
        elif label.lower().startswith(partial.lower()) and partial:
            score += 80
        
        # Fuzzy match using sequence matcher (even less important)
        elif partial:
            matcher = SequenceMatcher(None, partial.lower(), label.lower())
            ratio = matcher.ratio()
            score += ratio * 30
        
        # Context-specific scoring
        if context['is_import']:
            # For imports, prefer modules (kind 9)
            if kind == CompletionFilter.KIND_MODULE:
                score += 80
            else:
                score -= 30
        
        elif context['is_after_dot']:
            # After dot, prefer methods, properties, fields
            if kind in [CompletionFilter.KIND_METHOD, CompletionFilter.KIND_FUNCTION]:
                score += 40
            elif kind in [CompletionFilter.KIND_PROPERTY, CompletionFilter.KIND_FIELD]:
                score += 30
        
        elif context['is_blank_line']:
            # On blank lines, penalize random suggestions heavily
            if not partial:
                score -= 200
            # Prefer keywords and common patterns
            if kind == CompletionFilter.KIND_KEYWORD:
                score += 20
            elif kind in [CompletionFilter.KIND_CLASS, CompletionFilter.KIND_FUNCTION]:
                score += 10
        
        elif context['after_keyword'] == 'def':
            # After 'def', we're defining a function name - no suggestions needed
            score -= 500
        
        elif context['after_keyword'] == 'class':
            # After 'class', we're defining a class name - prefer capitalized or no suggestions
            if label[0].isupper():
                score += 20
            else:
                score -= 100
        
        # Prefer items with better sortText (LSP's own ranking)
        if sort_text:
            # Lower sortText values are better in LSP
            # Extract numeric part if present
            match = re.search(r'(\d+)', sort_text)
            if match:
                sort_priority = int(match.group(1))
                # Lower is better, so subtract
                score -= sort_priority / 100
        
        # Length penalty for very long completions when user typed little
        if partial and len(label) > len(partial) * 3:
            score -= 10
        
        return score
    
    @staticmethod
    def should_show_completions(context: dict, completions: list) -> bool:
        """Determine if completions should be shown at all."""
        # Don't show on completely blank lines with no partial word
        if context['is_blank_line'] and not context['partial_word']:
            logging.info("Suppressing completions: blank line with no input")
            return False
        
        # Don't show after 'def ' or 'class ' with no partial word
        if context['after_keyword'] in ['def', 'class'] and not context['partial_word']:
            logging.info(f"Suppressing completions: after '{context['after_keyword']}' keyword")
            return False
        
        # Must have at least one quality completion
        if not completions:
            return False
        
        return True
    
    @staticmethod
    def filter_and_sort(completions: list, text_before_cursor: str, min_score: float = -100) -> list:
        """Filter and sort completions based on relevance.
        
        Args:
            completions: Raw completion items from LSP
            text_before_cursor: Text before the cursor position
            min_score: Minimum relevance score to include (default -100)
        
        Returns:
            Filtered and sorted list of completion items
        """
        context = CompletionFilter.get_context(text_before_cursor)
        
        logging.info(f"Completion context: {context}")
        
        # Check if we should show completions at all
        if not CompletionFilter.should_show_completions(context, completions):
            return []
        
        # Calculate scores for all completions
        scored_completions = []
        for completion in completions:
            score = CompletionFilter.calculate_relevance_score(completion, context)
            if score >= min_score:
                scored_completions.append((score, completion))
                logging.debug(f"  {completion.get('label', '')}: score={score:.1f}")
        
        # Sort by score (highest first)
        scored_completions.sort(key=lambda x: x[0], reverse=True)
        
        # Log top scores for debugging
        if scored_completions:
            logging.info("Top scores:")
            for score, comp in scored_completions[:10]:
                logging.info(f"  {comp.get('label', '')}: {score:.1f}")
        
        # Return top items without scores
        filtered = [comp for score, comp in scored_completions[:20]]  # Limit to top 20
        
        logging.info(f"Filtered {len(completions)} completions down to {len(filtered)}")
        if filtered:
            top_labels = [c.get('label', '') for c in filtered[:5]]
            logging.info(f"Top 5: {top_labels}")
        
        return filtered