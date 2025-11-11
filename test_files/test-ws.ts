import WebSocket from 'ws';

const socket = new WebSocket('ws://localhost:8001/ws');

socket.on('open', () => {
    console.log('Connected to WebSocket server');
    socket.send(JSON.stringify({ msg: "WebSocket test message to port 8001"}));
})

socket.on('message', (data) => {
    console.log('Message from server:', data.toString());
});