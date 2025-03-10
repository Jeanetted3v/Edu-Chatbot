// src/frontend/api/routes/chat.js
const express = require('express');
const router = express.Router();

// Send a message
router.post('/messages', async (req, res) => {
  try {
    const { content, sender, sessionId } = req.body;
    
    // Forward to FastAPI backend
    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        sender,
        sessionId,
        timestamp: new Date()
      })
    });
    
    const data = await response.json();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get chat history for a session
router.get('/messages/:sessionId', async (req, res) => {
  const { sessionId } = req.params;
  // Fetch chat history
});

// Toggle human agent status
router.post('/session/toggle-agent', async (req, res) => {
  const { sessionId, isHumanAgent } = req.body;
  // Update session status
});

// Create new chat session
router.post('/session', async (req, res) => {
  // Create new session
});