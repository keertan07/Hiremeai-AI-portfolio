import React from 'react';

const Sidebar = ({ isOpen, toggleSidebar, chats, currentChatId, createNewChat, selectChat, disabled }) => {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <button className="new-chat-btn" onClick={createNewChat} disabled={disabled}>
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New chat
        </button>
        {/* Close button for mobile */}
        <button className="close-sidebar-btn" onClick={toggleSidebar}>
          <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div className="chat-history">
        <h3 className="history-label">Previous 30 Days</h3>
        {chats.map(chat => (
          <button
            key={chat.id}
            className={`history-btn ${chat.id === currentChatId ? 'active' : ''}`}
            onClick={() => selectChat(chat.id)}
            disabled={disabled}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <span className="history-title">{chat.title}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <a href="Resume.pdf" download className="resume-btn" target="_blank" rel="noreferrer">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          Download Resume
        </a>
      </div>
    </aside>
  );
};

export default Sidebar;
