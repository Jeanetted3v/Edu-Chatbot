


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    customer_id: str = Query(...),
    services: ServiceContainer = Depends(get_service_container)
):
    """Get existing session details

    Used by the client to check if a session is still active or to see which
    agent (bot or human) is currently handling it
    """
    session = await services.get_or_create_session(session_id, customer_id)
    
    return SessionResponse(
        session_id=session.session_id,
        customer_id=session.customer_id,
        current_agent=session.current_agent,
        start_time=session.start_time,
        last_interaction=session.last_interaction,
        message_count=session.message_count
    )


@router.get("/chat/history")
async def get_chat_history(
    session_id: str,
    customer_id: str,
    limit: int = Query(50, ge=1, le=100),
    services: ServiceContainer = Depends(get_service_container)
):
    """Get conversation history for a session
    
    Called when the chat UI fisrt loades to display previous messages.
    Used for periodic polling to check for new messages (especially when human
    agent is responding).
    Useful for resuming conversations after disconnections
    """
    try:
        chat_history = await services.get_chat_history(session_id, customer_id)
        history = await chat_history.get_last_n_turns(limit)
        
        # Convert to API format - using your ChatTurn model
        result = []
        for turn in history:
            chat_turn = ChatTurn(
                role=turn.get("role", MessageRole.SYSTEM),
                content=turn.get("content", ""),
                timestamp=turn.get("timestamp", datetime.now()),
                customer_id=customer_id,
                session_id=session_id,
                metadata=turn.get("metadata")
            )
            result.append(chat_turn)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
