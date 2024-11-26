import React from 'react';
import './App.css';
import ChatApp from './ChatApp.tsx'; // Import the ChatApp component

function App() {
    return (
        <div className="App" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <header className="App-header" style={{height: "100%"}}>
                <ChatApp />
            </header>
        </div>
    );
}

export default App;
