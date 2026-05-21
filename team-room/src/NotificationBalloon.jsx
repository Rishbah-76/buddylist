import { useEffect, useState } from "react";

/**
 * Windows XP Style Notification Balloon
 * 
 * Shows system tray balloons for:
 * - Teammate online/offline events
 * - New message notifications
 * - Connection status changes
 */

const BALLON_icons = {
  info: 'ℹ',
  success: '✓',
  warning: '⚠',
  error: '✕',
  online: '🟢',
  offline: '🔴',
  message: '💬',
};

export default function NotificationBalloon({ 
  notifications = [],
  onDismiss,
  autoDismissTime = 5000,
  maxVisible = 3,
}) {
  const [visibleNotifications, setVisibleNotifications] = useState([]);
  
  // Show new notifications
  useEffect(() => {
    if (notifications.length > 0) {
      const newVisible = notifications
        .filter(n => !visibleNotifications.some(v => v.id === n.id))
        .slice(-maxVisible);
      
      if (newVisible.length > 0) {
        setVisibleNotifications(prev => [...prev, ...newVisible]);
        
        // Auto-dismiss after timeout
        newVisible.forEach(n => {
          if (n.autoDismiss !== false) {
            setTimeout(() => {
              dismissNotification(n.id);
            }, autoDismissTime);
          }
        });
      }
    }
  }, [notifications]);

  const dismissNotification = (id) => {
    setVisibleNotifications(prev => prev.filter(n => n.id !== id));
    onDismiss?.(id);
  };

  if (visibleNotifications.length === 0) return null;

  return (
    <div className="notification-container" style={{
      position: 'fixed',
      bottom: '32px',
      right: '8px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column-reverse',
      gap: '4px',
    }}>
      {visibleNotifications.map(notification => (
        <NotificationBalloonItem 
          key={notification.id}
          notification={notification}
          onDismiss={() => dismissNotification(notification.id)}
        />
      ))}
    </div>
  );
}

function NotificationBalloonItem({ notification, onDismiss }) {
  const [isVisible, setIsVisible] = useState(false);
  
  // Entry animation
  useEffect(() => {
    setIsVisible(true);
  }, []);

  const icon = BALLON_icons[notification.type] || BALLON_icons.info;
  const title = notification.title || 'Notification';
  const message = notification.message || '';

  return (
    <div 
      className={`notification-balloon ${notification.type || 'info'}`}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateX(0)' : 'translateX(100%)',
        transition: 'all 0.3s ease-out',
        maxWidth: '280px',
        background: 'linear-gradient(180deg, #ffffe0 0%, #ffffcc 100%)',
        border: '1px solid #cca700',
        borderRadius: '4px',
        boxShadow: '2px 2px 4px rgba(0,0,0,0.3)',
        padding: '8px 12px',
        fontSize: '11px',
        fontFamily: '"Tahoma", "Arial", sans-serif',
        color: '#000',
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '8px',
      }}>
        <span style={{ fontSize: '16px', lineHeight: '1' }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{
            fontWeight: 'bold',
            marginBottom: '2px',
            fontSize: '11px',
            color: '#003399',
          }}>
            {title}
          </div>
          <div style={{
            color: '#333',
            fontSize: '11px',
            lineHeight: '1.3',
          }}>
            {message}
          </div>
        </div>
        <button 
          onClick={onDismiss}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '12px',
            color: '#666',
            padding: '0 2px',
            lineHeight: '1',
          }}
          title="Close"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

/**
 * Hook to manage notifications
 */
export function useNotifications() {
  const [notifications, setNotifications] = useState([]);
  
  const addNotification = (notification) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newNotification = {
      id,
      timestamp: Date.now(),
      ...notification,
    };
    setNotifications(prev => [...prev, newNotification]);
    return id;
  };
  
  const notifyTeammateOnline = (name, team) => {
    return addNotification({
      type: 'online',
      title: 'Teammate Online',
      message: `${name} joined ${team || 'the team'}`,
    });
  };
  
  const notifyTeammateOffline = (name) => {
    return addNotification({
      type: 'offline',
      title: 'Teammate Offline',
      message: `${name} has gone offline`,
    });
  };
  
  const notifyNewMessage = (from, preview) => {
    return addNotification({
      type: 'message',
      title: 'New Message',
      message: `${from}: ${preview?.substring(0, 50)}${preview?.length > 50 ? '...' : ''}`,
    });
  };
  
  const notifyError = (message) => {
    return addNotification({
      type: 'error',
      title: 'Connection Error',
      message,
    });
  };
  
  const dismissNotification = (id) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };
  
  const clearAll = () => {
    setNotifications([]);
  };
  
  return {
    notifications,
    addNotification,
    notifyTeammateOnline,
    notifyTeammateOffline,
    notifyNewMessage,
    notifyError,
    dismissNotification,
    clearAll,
  };
}