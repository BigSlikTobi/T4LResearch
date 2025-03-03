"""
Tests for the topic matcher functionality.
"""

import sys
import os
import unittest
import asyncio

# Add parent directories to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from topicManagement.topic_matcher import match_article_with_topics
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TestTopicMatcher(unittest.TestCase):
    """Test case for topic matching functionality."""
    
    def setUp(self):
        # Sample topics for testing
        self.test_topics = [
            {
                "id": 1, 
                "TopicName": "COMBINE",
                "isActive": True,
                "Description": "The NFL Combine is an annual event where college football players undergo physical and mental tests.",
                "Keywords": ["NFL", "Combine", "Scouting", "Evaluation", "Athleticism", "Draft"]
            },
            {
                "id": 2,
                "TopicName": "DRAFT",
                "isActive": True,
                "Description": "The NFL Draft is an annual event where NFL teams select new players from college football.",
                "Keywords": ["NFL", "Draft", "Prospects", "Pick", "Selection", "Round"]
            }
        ]
        
    def test_match_combine_topic(self):
        """Test matching an article about the NFL Combine."""
        article_headline = "Top Performers at the 2025 NFL Combine"
        article_content = """
        The 2025 NFL Combine in Indianapolis showcased an exceptional crop of talent this year.
        Notable standouts included quarterback John Smith, who impressed scouts with his arm strength and accuracy.
        Running back Mike Johnson recorded the fastest 40-yard dash time at 4.29 seconds.
        Several athletes improved their draft stock significantly through their combine performances.
        Teams will now adjust their draft boards based on these athletic evaluations.
        """
        
        # Match the article with topics
        matched_topic = match_article_with_topics(article_content, article_headline, self.test_topics)
        
        # Assert that it matched the COMBINE topic
        self.assertIsNotNone(matched_topic)
        self.assertEqual(matched_topic.get("TopicName"), "COMBINE")
    
    def test_match_draft_topic(self):
        """Test matching an article about the NFL Draft."""
        article_headline = "Team Needs Heading into the 2025 NFL Draft"
        article_content = """
        As the 2025 NFL Draft approaches, teams are finalizing their draft boards and addressing key needs.
        The Chicago Bears hold the first overall pick and are expected to select a quarterback.
        Several teams in the top 10 are looking to trade down to accumulate more picks.
        This draft class is considered particularly strong at offensive line and cornerback.
        Rounds 1-3 will take place on Thursday and Friday, with the remaining rounds on Saturday.
        """
        
        # Match the article with topics
        matched_topic = match_article_with_topics(article_content, article_headline, self.test_topics)
        
        # Assert that it matched the DRAFT topic
        self.assertIsNotNone(matched_topic)
        self.assertEqual(matched_topic.get("TopicName"), "DRAFT")
    
    def test_no_match(self):
        """Test an article that doesn't match any topic."""
        article_headline = "Regular Season Game Recap: Bears vs. Packers"
        article_content = """
        In a thrilling divisional matchup, the Chicago Bears defeated the Green Bay Packers 24-21 on Sunday.
        Quarterback Justin Fields threw for 285 yards and two touchdowns in the victory.
        The Bears' defense forced three turnovers, including a crucial interception in the fourth quarter.
        This win improves Chicago's record to 7-5, keeping their playoff hopes alive.
        The Packers fall to 6-6 and will face the Detroit Lions next week.
        """
        
        # Match the article with topics
        matched_topic = match_article_with_topics(article_content, article_headline, self.test_topics)
        
        # Assert that no match was found
        self.assertIsNone(matched_topic)

if __name__ == "__main__":
    unittest.main()