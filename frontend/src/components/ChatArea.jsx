import React, { useState, useRef, useEffect } from 'react';

const ChatArea = ({ theme, toggleTheme, toggleSidebar, isSidebarOpen, messages, isTyping, onSend }) => {
  const [input, setInput] = useState('');
  const chatBoxRef = useRef(null);

  const suggestedQuestions = [
    "What is Keertan's experience?",
    "What are Keertan's top skills?",
    "Tell me about Keertan's education.",
    "What projects has Keertan worked on?",
    "Why should we hire Keertan?"
  ];

  const scrollToBottom = () => {
    if (chatBoxRef.current) {
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;
    onSend(input);
    setInput('');
  };

  const isEmpty = messages.length === 0;

  return (
    <main className={`chat-area ${!isSidebarOpen ? 'expanded' : ''}`}>
      <header className="chat-header">
        <div className="header-left">
          {!isSidebarOpen && (
            <button className="hamburger-btn" onClick={toggleSidebar}>
              <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>
          )}
          <h1 className="header-title">Keertan's AI <span className="version-badge">Beta</span></h1>
        </div>
        
        <button className="theme-toggle" onClick={toggleTheme}>
          {theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode'}
        </button>
      </header>

      <div className="chat-box" ref={chatBoxRef}>
        {isEmpty ? (
          <div className="empty-state">
            <div className="logo-container">
              <div className="ai-logo">K</div>
            </div>
            <h2>How can I help you today?</h2>
            
            <div className="suggestions-grid">
              {suggestedQuestions.map((q, idx) => (
                <button 
                  key={idx} 
                  className="suggestion-card"
                  onClick={() => onSend(q)}
                  disabled={isTyping}
                >
                  <p>{q}</p>
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                  </svg>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages-container">
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-wrapper ${msg.sender}-message`}>
                <div className="message-avatar">
                  {msg.sender === 'ai' ? 'K' : 'U'}
                </div>
                <div className="message-content">
                  {msg.text}
                </div>
              </div>
            ))}
            
            {isTyping && (
              <div className="message-wrapper ai-message">
                <div className="message-avatar">K</div>
                <div className="message-content typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="chat-input-area">
        <form className="chat-form" onSubmit={handleSubmit}>
          <input 
            type="text" 
            className="chat-input" 
            placeholder="Message Keertan's AI..." 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isTyping}
          />
          <button type="submit" className="send-btn" disabled={isTyping || !input.trim()}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="20" height="20">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </form>
        <p className="disclaimer">AI can make mistakes. Verify important information from the resume.</p>
      </div>
    </main>
  );
};

export default ChatArea;
