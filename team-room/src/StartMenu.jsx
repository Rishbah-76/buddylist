import { useEffect, useRef, useState } from "react";

/**
 * Windows XP Style Start Menu
 * 
 * Shows a popup menu from the Start button with:
 * - Current user info
 * - Team selector (switch between teams)
 * - Quick launch items
 * - Settings and help links
 * - Log off / shutdown options
 */
export default function StartMenu({ 
  isOpen, 
  onClose, 
  currentTeam, 
  availableTeams = [], 
  onTeamChange,
  displayName 
}) {
  const menuRef = useRef(null);
  const [selectedItem, setSelectedItem] = useState(null);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        const startButton = document.querySelector('.start-button');
        if (startButton && !startButton.contains(event.target)) {
          onClose();
        }
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleTeamSelect = (team) => {
    onTeamChange(team);
    onClose();
  };

  return (
    <div 
      ref={menuRef}
      className="start-menu"
      style={{
        position: 'absolute',
        bottom: '28px',
        left: '0',
        zIndex: 1000,
      }}
    >
      {/* Side panel with user info */}
      <div className="start-menu-sidebar">
        <div className="start-menu-user-bg">
          <div className="start-menu-user-icon">
            👤
          </div>
        </div>
        <div className="start-menu-username">
          {displayName || 'User'}
        </div>
      </div>
      
      {/* Main menu items */}
      <div className="start-menu-main">
        {/* Team Switcher Section */}
        {(availableTeams.length > 0) && (
          <div className="start-menu-section">
            <div className="start-menu-section-header">Teams</div>
            {availableTeams.map(team => (
              <button
                key={team}
                className={`start-menu-item ${team === currentTeam ? 'current' : ''}`}
                onClick={() => handleTeamSelect(team)}
                onMouseEnter={() => setSelectedItem(team)}
                onMouseLeave={() => setSelectedItem(null)}
              >
                <span className="start-menu-item-icon">
                  {team === currentTeam ? '✓' : '○'}
                </span>
                <span className="start-menu-item-label">{team}</span>
              </button>
            ))}
          </div>
        )}
        
        <div className="start-menu-separator" />
        
        {/* Quick Launch */}
        <div className="start-menu-section">
          <button 
            className="start-menu-item"
            onClick={() => {
              // Open new teammate window
              onClose();
            }}
          >
            <span className="start-menu-item-icon">📂</span>
            <span className="start-menu-item-label">New Teammate Chat</span>
          </button>
          
          <button className="start-menu-item">
            <span className="start-menu-item-icon">🔍</span>
            <span className="start-menu-item-label">Find Teammates</span>
          </button>
        </div>
        
        <div className="start-menu-separator" />
        
        {/* Programs */}
        <div className="start-menu-section">
          <div className="start-menu-item start-menu-item-parent">
            <span className="start-menu-item-icon">📝</span>
            <span className="start-menu-item-label">Programs</span>
            <span className="start-menu-item-arrow">▶</span>
          </div>
          
          <div className="start-menu-item start-menu-item-parent">
            <span className="start-menu-item-icon">�Documents</span>
            <span className="start-menu-item-label">My Documents</span>
            <span className="start-menu-item-arrow">▶</span>
          </div>
        </div>
        
        <div className="start-menu-separator" />
        
        {/* Settings */}
        <div className="start-menu-section">
          <button className="start-menu-item">
            <span className="start-menu-item-icon">⚙</span>
            <span className="start-menu-item-label">Settings</span>
          </button>
          
          <button className="start-menu-item">
            <span className="start-menu-item-icon">❓</span>
            <span className="start-menu-item-label">Help and Support</span>
          </button>
          
          <button className="start-menu-item">
            <span className="start-menu-item-icon">🔎</span>
            <span className="start-menu-item-label">Search...</span>
          </button>
        </div>
        
        <div className="start-menu-separator" />
        
        {/* Log off */}
        <div className="start-menu-section">
          <button className="start-menu-item">
            <span className="start-menu-item-icon">🔓</span>
            <span className="start-menu-item-label">Log Off {displayName || 'User'}...</span>
          </button>
          
          <button className="start-menu-item">
            <span className="start-menu-item-icon">⏻</span>
            <span className="start-menu-item-label">Turn Off Computer</span>
          </button>
        </div>
      </div>
    </div>
  );
}