import { writable } from 'svelte/store';

function createWebSocketStore() {
  const { subscribe, set, update } = writable({
    connected: false,
    messages: []
  });

  let ws = null;

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      update(state => ({ ...state, connected: true }));
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      update(state => ({
        ...state,
        messages: [...state.messages, message]
      }));
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      update(state => ({ ...state, connected: false }));
      // Attempt to reconnect after 3 seconds
      setTimeout(() => connect(), 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  function send(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }

  return {
    subscribe,
    connect,
    send
  };
}

export const websocket = createWebSocketStore();
