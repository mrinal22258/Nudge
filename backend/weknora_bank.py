import re
from typing import Dict, Any, List, Optional

# Curated Seed Question Bank (34 questions)
QUESTION_BANK = [
    # Coding Questions (Data Structures & Algorithms)
    {
        "id": "code_1",
        "topic": "Arrays & Hashing (Two Sum / Group Anagrams)",
        "type": "coding",
        "difficulty": "easy",
        "prompt_text": "Write a function that takes an array of strings and groups anagrams together. For example, input ['eat', 'tea', 'tan', 'ate', 'nat', 'bat'] should return [['bat'], ['nat', 'tan'], ['ate', 'eat', 'tea']]. Draw the logic flow and write the code on the canvas.",
        "expected_approach_notes": "A strong answer should use a hash map where keys are the sorted strings or char count tuples, and values are lists of anagrams. The candidate should mention O(N * K log K) complexity (or O(N * K) with char count arrays) and verify edge cases like empty arrays or empty strings."
    },
    {
        "id": "code_2",
        "topic": "Sliding Window / Subarrays",
        "type": "coding",
        "difficulty": "medium",
        "prompt_text": "Find the length of the longest substring without repeating characters. Draw the sliding window pointers (left and right) on the canvas, trace how they move, and write the code.",
        "expected_approach_notes": "A strong answer uses a sliding window (two pointers) and a set or hash map to track character indices. Time complexity should be O(N) and space complexity O(min(M, N)). Candidate must explain how the left pointer moves when a duplicate character is found."
    },
    {
        "id": "code_3",
        "topic": "Linked Lists (Detect Cycle)",
        "type": "coding",
        "difficulty": "medium",
        "prompt_text": "Given a head pointer to a linked list, write a function to detect if the list contains a cycle. Sketch a linked list with a loop on the board, show your pointers, and write the code.",
        "expected_approach_notes": "A strong answer uses Floyd's Cycle-Finding Algorithm (slow and fast pointers moving at 1x and 2x speeds). Candidate must explain why the pointers are guaranteed to meet if a cycle exists (O(N) time, O(1) space) and handle null checks."
    },
    {
        "id": "code_4",
        "topic": "Binary Trees (Lowest Common Ancestor)",
        "type": "coding",
        "difficulty": "medium",
        "prompt_text": "Find the Lowest Common Ancestor (LCA) of two nodes in a Binary Tree. Sketch the tree layout, indicate node relations, and write the recursive implementation.",
        "expected_approach_notes": "A strong answer uses a post-order DFS traversal. If root is null or matches node p or q, return root. Recurse left and right. If left and right recursions return non-null, the current root is the LCA. Time complexity O(N), space complexity O(H) recursion stack."
    },
    {
        "id": "code_5",
        "topic": "Dynamic Programming (Coin Change)",
        "type": "coding",
        "difficulty": "hard",
        "prompt_text": "You are given coins of different denominations and a total amount of money. Write a function to compute the fewest number of coins needed to make up that amount. Sketch the DP state table and write the code.",
        "expected_approach_notes": "A strong answer uses bottom-up iterative DP with a 1D array of size amount + 1. Transition: dp[i] = min(dp[i], dp[i - coin] + 1) for each coin. Candidate must handle the base case amount=0 and target amounts that cannot be formed (returning -1). Complexity O(Amount * Coins)."
    },
    {
        "id": "code_6",
        "topic": "Sorting & Searching (Merge Intervals)",
        "type": "coding",
        "difficulty": "medium",
        "prompt_text": "Given an array of intervals where intervals[i] = [start_i, end_i], merge all overlapping intervals. Draw the sorted intervals on the canvas to illustrate the merge operation and write the code.",
        "expected_approach_notes": "A strong answer starts by sorting intervals by their start time (O(N log N)). It then iterates through the intervals, checking if the current interval starts after the last merged interval ends. If so, append it; otherwise, update the end time of the last merged interval."
    },
    {
        "id": "code_7",
        "topic": "Graphs (NumberOf Islands / DFS / BFS)",
        "type": "coding",
        "difficulty": "medium",
        "prompt_text": "Given an m x n 2D binary grid representing a map of '1's (land) and '0's (water), return the number of islands. Draw a sample grid on the canvas, color/label the islands, and write the DFS or BFS traversal code.",
        "expected_approach_notes": "A strong answer visits land cells and triggers a flood fill (DFS/BFS) to mark all connected land cells as visited (e.g. by mutating to '0' or keeping a visited set). Time complexity O(M * N) and space complexity O(M * N) for the recursion stack/queue."
    },
    {
        "id": "code_8",
        "topic": "Stacks & Queues (Valid Parentheses)",
        "type": "coding",
        "difficulty": "easy",
        "prompt_text": "Write a function that validates string brackets: (), [], {}. The brackets must close in the correct order. Draw a stack visualization showing pushes and pops, and write the code.",
        "expected_approach_notes": "A strong answer uses a stack. Open brackets are pushed. Closing brackets are matched against the top of the stack using a hash map for lookups. O(N) time and O(N) space. Must handle empty stack pop scenarios."
    },

    # System Design Questions
    {
        "id": "sys_1",
        "topic": "Scalability / URL Shortener (TinyURL)",
        "type": "system_design",
        "difficulty": "medium",
        "prompt_text": "Design a high-scale URL shortening service like TinyURL. Draw the system architecture diagram on the canvas, showing the API Gateway, Web Servers, Database, Cache, and unique ID generator. Explain your schema and database choice.",
        "expected_approach_notes": "A strong answer covers: hash generation (Base62 encoding of a counter or auto-incrementing ID), database storage (NoSQL like MongoDB or Key-Value for rapid read-write, SQL is also acceptable), caching layer (Redis) for hot URLs, API designs, and handling 10,000+ QPS."
    },
    {
        "id": "sys_2",
        "topic": "Distributed Caching (Memcached / Redis Cluster)",
        "type": "system_design",
        "difficulty": "medium",
        "prompt_text": "Design a distributed caching system that handles 1 million reads per second. Draw a diagram illustrating consistent hashing, write-through vs write-back caching policies, and high-availability replica groups.",
        "expected_approach_notes": "A strong answer discusses Consistent Hashing (DHT) to distribute keys across cache nodes, virtual nodes to prevent hot spots, replication (Master-Replica), cache eviction policies (LRU/LFU), and cache stampede prevention (mutex locks)."
    },
    {
        "id": "sys_3",
        "topic": "Message Queues / Real-time Notification System",
        "type": "system_design",
        "difficulty": "medium",
        "prompt_text": "Design a push notification service that sends billions of notifications daily (SMS, Email, Push) with low latency. Draw the message ingestion, queuing layer, priority queues, worker nodes, and gateway delivery engines.",
        "expected_approach_notes": "A strong answer uses Message Queues (Kafka/RabbitMQ) for decoupling, priority routing (important alerts vs marketing notifications), tracking delivery status, storing device tokens, rate-limiting to avoid spamming users, and throttling APIs."
    },
    {
        "id": "sys_4",
        "topic": "Web Services / Real-time Collaboration Engine (Google Docs)",
        "type": "system_design",
        "difficulty": "hard",
        "prompt_text": "Design a real-time collaborative text editor like Google Docs. Draw the client-server sync loop, showing how concurrent edits are merged. Discuss Operational Transformation (OT) or Conflict-Free Replicated Data Types (CRDTs).",
        "expected_approach_notes": "A strong answer details WebSockets for real-time bi-directional transport, Operational Transformation (OT) resolving conflict via a central server or CRDTs for peer-to-peer, keeping snapshot storage in document databases, and handling offline synchronization."
    },
    {
        "id": "sys_5",
        "topic": "Data Ingestion / Web Crawler",
        "type": "system_design",
        "difficulty": "medium",
        "prompt_text": "Design a web crawler that scans the entire internet and indexes text content. Draw a diagram of the Link Queue, HTML Downloader, Content Parser, Duplicate Filter (Bloom Filter), and Document Store.",
        "expected_approach_notes": "A strong answer includes: Robots.txt checker, Bloom Filters for URL duplicate detection, DNS cache, multi-threaded workers, distributed storage (HDFS/S3), indexing (ElasticSearch), and polite crawling algorithms (rate limiting per domain)."
    },
    {
        "id": "sys_6",
        "topic": "API Design / Ride-Sharing App (Uber/Lyft)",
        "type": "system_design",
        "difficulty": "hard",
        "prompt_text": "Design a ride-sharing system (Uber/Lyft). Sketch the mapping/spatial indexing layer (e.g. Quadtree or Uber H3), the driver tracking broker, and how rider-driver matchmaking operates.",
        "expected_approach_notes": "A strong answer uses geospatial databases or indexing (Geohash, H3, Quadtree) for matching nearby drivers. Discusses storing active driver coordinates in memory (Redis), WebSockets/gRPC for location updates, and handling surge pricing."
    },
    {
        "id": "sys_7",
        "topic": "Databases / E-Commerce Flash Sale System",
        "type": "system_design",
        "difficulty": "hard",
        "prompt_text": "Design an e-commerce backend to handle a flash sale with 500,000 requests per second. Draw the cache-in-front database architecture, showing how inventory decrementing is decoupled to prevent database locks.",
        "expected_approach_notes": "A strong answer utilizes Redis Lua scripts for atomic inventory checks and decs in memory, redirects orders into a queue for asynchronous payment and fulfillment, implements rate limiting, and avoids row locks on relational tables."
    },
    {
        "id": "sys_8",
        "topic": "Storage Systems / Large File CDN (Netflix / YouTube)",
        "type": "system_design",
        "difficulty": "medium",
        "prompt_text": "Design a video-streaming infrastructure (Netflix). Draw the content ingestion pipeline (video encoding/transcoding), file storage (S3), and distributed Content Delivery Network (CDN) edge cache redirection.",
        "expected_approach_notes": "A strong answer details how videos are chunked and encoded into multiple bitrates/resolutions (DASH/HLS), how CDNs cache popular files near users, the user database, search index, and metadata synchronization."
    },

    # Behavioral & System Engineering Questions
    {
        "id": "beh_1",
        "topic": "Conflict Resolution / Working with stakeholders",
        "type": "behavioral",
        "difficulty": "easy",
        "prompt_text": "Describe a situation where you had a major disagreement with a tech lead or product manager regarding an implementation detail. Draw a timeline or flowchart of your communication and resolution steps.",
        "expected_approach_notes": "A strong answer uses the STAR method (Situation, Task, Action, Result). It shows professional empathy, backing up arguments with facts/metrics (running a benchmark or mock), aligning on product goals, and disagreeing-and-committing constructively."
    },
    {
        "id": "beh_2",
        "topic": "Handling Tech Debt / Refactoring",
        "type": "behavioral",
        "difficulty": "medium",
        "prompt_text": "Talk about a project where you inherited significant legacy technical debt. Draw a block diagram showing the legacy dependency layout and how you phased your refactoring process without disrupting production.",
        "expected_approach_notes": "A strong answer covers identifying the debt (high error rate, slow dev speed), drawing boundary lines (strangler pattern), writing integration tests to guarantee regression-safety, and executing migrations incrementally."
    },
    {
        "id": "beh_3",
        "topic": "Mentorship / Team Growth",
        "type": "behavioral",
        "difficulty": "easy",
        "prompt_text": "Describe how you onboarded and mentored a junior team member. Draw a workflow showing your feedback loops, pair programming, and code review checkpoints.",
        "expected_approach_notes": "A strong answer displays leadership, structure, and emotional intelligence. Discusses breaking down tasks into chewable sizes, defining clear definition of done, conducting supportive code reviews, and fostering psychological safety."
    },
    {
        "id": "beh_4",
        "topic": "Incident Management / Post-Mortems",
        "type": "behavioral",
        "difficulty": "medium",
        "prompt_text": "Describe a severe production outage you were responsible for or had to debug. Draw a timeline showing the incident start, detection, triage, mitigation, and the 5-Whys root cause analysis.",
        "expected_approach_notes": "A strong answer remains blameless. Focuses on rapid mitigation (rollback) before debugging. Shows analytical triage (searching log metrics). Outlines post-mortem action items (testing, alerts) to prevent occurrence."
    },
    {
        "id": "beh_5",
        "topic": "Project Delivery / Managing Scopes",
        "type": "behavioral",
        "difficulty": "medium",
        "prompt_text": "Share a time when a critical project deadline was at risk of slipping. Draw a Gantt chart or scope-cut diagram showing how you renegotiated boundaries with PMs and engineers to ship on time.",
        "expected_approach_notes": "A strong answer shows proactive communication. Discusses identifying critical paths, negotiating the cut of nice-to-have features, re-allocating tasks, keeping stakeholders informed, and maintaining quality standards."
    },
    {
        "id": "beh_6",
        "topic": "Architectural Tradeoffs (SQL vs NoSQL)",
        "type": "behavioral",
        "difficulty": "medium",
        "prompt_text": "Explain a scenario where you had to choose between a Relational Database (SQL) and a Document/NoSQL database. Draw a comparison matrix on the canvas showing Schema, Scalability, Transactions, and query patterns.",
        "expected_approach_notes": "A strong answer discusses ACID compliance, structured tabular schemas vs flexible documents, horizontal partitioning (sharding) vs vertical scaling, and specific trade-offs (e.g. read latency vs write availability)."
    },
    {
        "id": "beh_7",
        "topic": "Prioritization / Handling Multiple Streams",
        "type": "behavioral",
        "difficulty": "easy",
        "prompt_text": "How do you manage your time when assigned to multiple high-priority development streams concurrently? Draw your priority matrix (e.g., Eisenhower Matrix) and show how you schedule focus blocks.",
        "expected_approach_notes": "A strong answer shows focus structure. Uses calendars for deep work blocks, utilizes Kanban metrics, communicates blockers immediately, delegates tasks when appropriate, and aligns tasks to business value."
    },
    {
        "id": "beh_8",
        "topic": "Security / Mitigating Vulnerabilities",
        "type": "behavioral",
        "difficulty": "medium",
        "prompt_text": "Describe a time when you audited a security vulnerability (e.g. XSS, SQL injection, API exposure). Draw the request/response sequence showing the vulnerability exploit path and how you patched it.",
        "expected_approach_notes": "A strong answer identifies OWASP Top 10 vulnerabilities, discusses input validation, parameterized queries, escaping scripts, rate limiting, token headers, and implementing static code analysis (SAST)."
    },
    # Finance Questions
    {
        "id": "fin_1",
        "topic": "Derivative Pricing & Risk Hedging (Black-Scholes / Delta Hedging)",
        "type": "finance",
        "difficulty": "hard",
        "prompt_text": "Design a delta-hedging simulation for a European Call Option. Draw the hedging loop, the relationship between the stock price, option price, and delta, and write a Python function that calculates delta using the Black-Scholes formula. Discuss how transaction costs and discrete-time rebalancing affect the hedging error.",
        "expected_approach_notes": "A strong answer outlines the formula for d1 and Delta (N(d1)), demonstrates how delta changes with spot price and time to maturity, shows a schematic of a portfolio consisting of long option / short delta * stock, and details how daily/weekly rebalancing introduces tracking error/hedging variance."
    },
    {
        "id": "fin_2",
        "topic": "High-Frequency Order Book Simulation & Market Making",
        "type": "finance",
        "difficulty": "medium",
        "prompt_text": "Design a limit order book (LOB) matching engine. Draw the data structures for bids, asks (price-time priority), and active orders. Write the pseudo-code for submitting a limit order and matching it against the book. Explain how you would optimize the time complexity to O(1) for execution.",
        "expected_approach_notes": "A strong answer uses a doubly linked list for order queues at each price level and a binary search tree (or hash map) for indexing price levels. Submitted orders match greedily. Time complexity must be analyzed (BST: O(log M), Hash Map: O(1) for lookups)."
    },
    {
        "id": "fin_3",
        "topic": "Portfolio Risk & Performance Metrics (Value at Risk / VaR)",
        "type": "finance",
        "difficulty": "medium",
        "prompt_text": "Design a framework to calculate the 99% 1-day Value at Risk (VaR) for a portfolio containing multiple assets. Draw the calculation pipeline (data extraction, return calculations, covariance mapping, risk estimation). Write a Python function using historical simulation to compute VaR. Discuss the limitations of historical simulation versus parametric VaR.",
        "expected_approach_notes": "A strong answer covers calculating daily asset returns, multiplying weights by returns, sorting returns to find the 1st percentile (99% VaR), and explaining the difference/limitations of Parametric (normal distribution assumption) vs Historical (fat tails, regime changes)."
    },
    # AI/ML Engineering Questions
    {
        "id": "ai_1",
        "topic": "Retrieval-Augmented Generation (RAG) Architecture",
        "type": "ai_engineering",
        "difficulty": "hard",
        "prompt_text": "Design an enterprise RAG system that runs on top of 10 million documents. Draw the ingestion pipeline (document chunking, semantic parsing, embedding generation, vector database indexing) and the runtime query flow (dense retrieval, reranking, and generation with safety guardrails). Explain how you evaluate retrieval precision and generation hallucinations.",
        "expected_approach_notes": "A strong answer covers chunking strategies (overlapping), vector DB (HNSW or IVF-PQ index), using a cross-encoder reranker, context size management, safety guardrails (toxic filters), and evaluation frameworks like Ragas (faithfulness, answer relevance)."
    },
    {
        "id": "ai_2",
        "topic": "Multi-Head Attention Mechanism from Scratch",
        "type": "ai_engineering",
        "difficulty": "medium",
        "prompt_text": "Implement the Scaled Dot-Product Attention module in PyTorch. Draw a matrix-multiplication flow diagram showing Query (Q), Key (K), and Value (V) tensors, the scaling factor, the softmax operation, and output multiplication. Write the PyTorch code including masks for causal decoding.",
        "expected_approach_notes": "A strong answer correctly computes Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) * V. Code should be clean, handling batched tensors, causal masking (replacing upper triangle with -inf), and verifying shapes at each step."
    },
    {
        "id": "ai_3",
        "topic": "Real-time Object Detection Pipeline (YOLO/SSD)",
        "type": "ai_engineering",
        "difficulty": "hard",
        "prompt_text": "Design a real-time object detection system for autonomous driving cameras (e.g. YOLO/SSD pipeline). Draw the video frame ingestion, feature extraction backbone, neck, prediction head, and Non-Maximum Suppression (NMS) block. Write Python code implementing the NMS algorithm. Discuss latency optimization strategies (quantization, edge deployment).",
        "expected_approach_notes": "A strong answer covers YOLO/SSD single-shot architectures, box regression, confidence scores, and IoU calculation. The NMS code must sort boxes by score, greedily select the highest score, and discard overlaps above an IoU threshold."
    },
    # Product Management Questions
    {
        "id": "pm_1",
        "topic": "Product Design & Metrics (Ride-sharing for Kids)",
        "type": "product_management",
        "difficulty": "medium",
        "prompt_text": "Design a ride-sharing service tailored specifically for children (school commutes, extracurriculars). Draw the user flow for parents and drivers, and identify key safety features. Define the North Star metric for this service, along with 3 supporting metrics (acquisition, retention, safety) and 1 guardrail metric.",
        "expected_approach_notes": "A strong answer uses a clear user-centric framework (e.g., CIRCLES or HEART). Identifies trust and safety (background checks, tracking, notifications) as primary concerns. North Star: Completed Safe Rides. Supporting: active users, driver retention. Guardrail: ride cancellation rate."
    },
    {
        "id": "pm_2",
        "topic": "Product Strategy & Growth (YouTube Shorts)",
        "type": "product_management",
        "difficulty": "medium",
        "prompt_text": "Design a growth strategy to increase creator engagement and viewer retention on YouTube Shorts. Draw the creator/viewer flywheel, listing specific product features you would launch. Outline a monetization framework and explain the metrics you'd track to validate success.",
        "expected_notes": "A strong answer identifies user segments (casual creators, professional creators, viewers) and their pain points. Proposes features like simplified audio editing, creator revenue sharing, and personalized feed algorithmic improvements. Flywheel: Creator Uploads -> Viewer Engagement -> Ads/Monetization -> Creator Payout."
    },
    {
        "id": "pm_3",
        "topic": "Fermi Estimation & Metrics (EV Charging Market Entry)",
        "type": "product_management",
        "difficulty": "medium",
        "prompt_text": "Estimate the market size (annual revenue) for EV charging stations in New York City. Draw the estimation tree/structure, showing your assumptions for the number of EVs, average charging frequency, electricity cost, and charging markup. Identify 3 critical metrics to track if you were launching this business.",
        "expected_approach_notes": "A strong answer uses a structured tree to break down NYC population -> car owners -> EV owners -> charging frequency (home vs public) -> public charging price per kWh -> annual revenue. Critical metrics: Charger utilization rate, customer acquisition cost (CAC), average margin per charge."
    }
]

import math
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "and", "of", "to", "in", "is", "for", "that", "it", "on", "with",
    "as", "at", "by", "be", "this", "are", "from", "or", "you", "your", "can", "we", "us"
}

def tokenize(text: str) -> List[str]:
    tokens = re.findall(r'\w+', text.lower())
    return [t for t in tokens if t not in STOPWORDS]

def _build_idf(corpus_texts: List[str]) -> Dict[str, float]:
    doc_count = len(corpus_texts)
    df = Counter()
    for text in corpus_texts:
        for term in set(tokenize(text)):
            df[term] += 1
    return {term: math.log((1 + doc_count) / (1 + freq)) + 1 for term, freq in df.items()}

# Build corpus text and IDF cache at module load
q_texts = []
for q in QUESTION_BANK:
    parts = [q.get("topic", ""), q.get("prompt_text", "")]
    if "expected_approach_notes" in q:
        parts.append(q["expected_approach_notes"])
    if "expected_notes" in q:
        parts.append(q["expected_notes"])
    q_texts.append(" ".join(parts))

IDF_CACHE = _build_idf(q_texts)

def get_tfidf_cosine_similarity(text1: str, text2: str, idf: Dict[str, float]) -> float:
    def tf_vector(text):
        tokens = tokenize(text)
        tf = Counter(tokens)
        return {term: count * idf.get(term, 1.0) for term, count in tf.items()}
    
    v1, v2 = tf_vector(text1), tf_vector(text2)
    if not v1 or not v2:
        return 0.0
        
    dot_product = sum(v1[t] * v2.get(t, 0.0) for t in v1)
    norm1 = math.sqrt(sum(v**2 for v in v1.values()))
    norm2 = math.sqrt(sum(v**2 for v in v2.values()))
    
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot_product / (norm1 * norm2)

def get_cosine_similarity(text1: str, text2: str) -> float:
    """Compare similarity between two texts using a lightweight TF-IDF cosine similarity."""
    return get_tfidf_cosine_similarity(text1, text2, IDF_CACHE)

def retrieve_question(gap_profile: Any, interview_type: str) -> Dict[str, Any]:
    """Retrieve the most relevant question from the seed bank based on gap profile and interview type."""
    # Filter questions by type
    typed_questions = [q for q in QUESTION_BANK if q["type"] == interview_type]
    if not typed_questions:
        # Fallback to any question of this type, or any question at all
        typed_questions = [q for q in QUESTION_BANK if q["type"] == "coding"]

    # Grab the top gap topics robustly
    top_gaps = []
    if isinstance(gap_profile, dict):
        # Extract the first list found in values (e.g. {"gaps": [...]})
        for val in gap_profile.values():
            if isinstance(val, list):
                gap_profile = val
                break

    if isinstance(gap_profile, list):
        for g in gap_profile:
            if isinstance(g, dict):
                topic = g.get("topic")
                importance = g.get("importance", "high")
                if topic and importance in ["high", "medium"]:
                    top_gaps.append(topic)
            elif isinstance(g, str):
                top_gaps.append(g)

    if not top_gaps:
        # If no explicit gaps, return the first question of this type
        return typed_questions[0]
        
    gap_query = " ".join(top_gaps)
    
    # Rank questions by cosine similarity to the gap query
    scored_questions = []
    for q in typed_questions:
        # Match against topic and prompt_text
        match_text = f"{q['topic']} {q['prompt_text']}"
        score = get_cosine_similarity(gap_query, match_text)
        scored_questions.append((q, score))
        
    scored_questions.sort(key=lambda x: x[1], reverse=True)
    return scored_questions[0][0]

def retrieve_top_questions(gap_profile: Any, interview_type: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Retrieve the top matching questions ranked by gap similarity."""
    typed_questions = [q for q in QUESTION_BANK if q["type"] == interview_type]
    if not typed_questions:
        typed_questions = [q for q in QUESTION_BANK if q["type"] == "coding"]

    top_gaps = []
    if isinstance(gap_profile, dict):
        for val in gap_profile.values():
            if isinstance(val, list):
                gap_profile = val
                break

    if isinstance(gap_profile, list):
        for g in gap_profile:
            if isinstance(g, dict):
                topic = g.get("topic")
                importance = g.get("importance", "high")
                if topic and importance in ["high", "medium"]:
                    top_gaps.append(topic)
            elif isinstance(g, str):
                top_gaps.append(g)

    if not top_gaps:
        return typed_questions[:limit]
        
    gap_query = " ".join(top_gaps)
    
    scored_questions = []
    for q in typed_questions:
        match_text = f"{q['topic']} {q['prompt_text']}"
        score = get_cosine_similarity(gap_query, match_text)
        scored_questions.append((q, score))
        
    scored_questions.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored_questions[:limit]]


def retrieve_grounding_notes(question_id: str, canvas_content: str) -> str:
    """Retrieve expected approach notes, possibly filtering or returning the full text to ground follow-ups."""
    # Find matching question
    question = next((q for q in QUESTION_BANK if q["id"] == question_id), None)
    if not question:
        return "No specific guidelines available."
        
    # Return expected notes (can be extended to retrieve specific sentences matched with canvas text)
    return question["expected_approach_notes"]


def generate_dynamic_question(
    resume_structured: Dict[str, Any], 
    jd_structured: Dict[str, Any], 
    gap_profile: List[Dict[str, Any]], 
    interview_type: str, 
    exclude_topics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Generates a custom mock interview question targeting candidate gaps for the specified type using Ollama."""
    import ollama
    import uuid
    import json
    client = ollama.Client(host="http://localhost:11434")
    
    # Format gaps and context
    gaps_str = json.dumps(gap_profile, indent=2)
    exclude_topics = exclude_topics or []
    exclude_clause = f" Do NOT generate a question on any of these topics: {exclude_topics}." if exclude_topics else ""
    
    prompt = f"""You are an elite technical interviewer. You need to dynamically construct a single custom whiteboard mock interview question for a candidate.
The question must target the gaps between the candidate's background and the job requirements, specifically tailored to the selected interview track.

Selected Interview Track: {interview_type}
Candidate Target Gaps Profile:
{gaps_str}

Candidate Background:
{json.dumps(resume_structured, indent=2)}

Target Job Description:
{json.dumps(jd_structured, indent=2)}
{exclude_clause}

Your task:
1. Identify the most critical technical/domain knowledge gaps from the profiles.
2. Formulate a challenging, realistic whiteboard mock interview question of type '{interview_type}' that addresses those gaps.
   - If '{interview_type}' is 'coding', the question must ask the candidate to implement an algorithm or data structure from scratch, sketch the logic flow, and write clean code on the canvas.
   - If '{interview_type}' is 'system_design', the question must ask the candidate to design a scalable architecture, drawing components (load balancers, databases, etc.) on the canvas.
   - If '{interview_type}' is 'behavioral', the question must ask the candidate to detail a professional scenario (using the STAR method) and draw a timeline or flowchart of their steps.
   - If '{interview_type}' is 'finance', the question must ask the candidate to outline pricing models, delta hedging loops, limit order books, or portfolio risk calculations, drawing the logic flow on the canvas.
   - If '{interview_type}' is 'ai_engineering', the question must ask the candidate to design/implement a machine learning pipeline, RAG architecture, attention mechanism, or deep learning block.
   - If '{interview_type}' is 'product_management', the question must ask the candidate to design a product user flow, strategy flywheel, metrics dashboard, or Fermi estimation tree.
3. Provide a concise topic title for the question.
4. Provide a detailed prompt text explaining the whiteboard scenario to the candidate.
5. Provide expected approach/solution notes (the key concepts, formulas, algorithms, or components the candidate MUST cover to pass).

Return ONLY a valid JSON object matching the following structure:
{{
  "topic": "Name of the topic (string)",
  "difficulty": "medium" or "hard" (string),
  "prompt_text": "Detailed prompt text to display to the candidate explaining the whiteboard question scenario (string)",
  "expected_approach_notes": "Detailed notes on what a strong answer/solution should cover on the whiteboard and in explanation (string)"
}}"""

    try:
        response = client.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "system", "content": "You are a precise interview question designer. Return only a valid JSON object matching the requested schema."},
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.4, "num_ctx": 4096},
            format="json"
        )
        content = response["message"]["content"].strip()
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
        result = json.loads(content)
        return {
            "id": f"dyn_{str(uuid.uuid4())}",
            "topic": result.get("topic", "Dynamic Whiteboard Challenge"),
            "type": interview_type,
            "difficulty": result.get("difficulty", "medium"),
            "prompt_text": result.get("prompt_text", "Please sketch your approach on the whiteboard and write your solution."),
            "expected_approach_notes": result.get("expected_approach_notes", "Provide a structured explanation of the problem, analyze tradeoffs, and implement clean code or systems diagram.")
        }
    except Exception as e:
        print(f"[Dynamic Question Gen Error] {e}")
        # Fallback question
        typed_questions = [q for q in QUESTION_BANK if q["type"] == interview_type]
        if not typed_questions:
            typed_questions = [q for q in QUESTION_BANK if q["type"] == "coding"]
        return typed_questions[0]

