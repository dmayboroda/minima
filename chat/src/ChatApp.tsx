import React, { useState, useEffect } from 'react';
import { TextField, List, ListItem, ListItemText, Box, AppBar, Toolbar, Typography } from '@mui/material';

interface Message {
    type: 'answer' | 'question' | 'full',
    reporter: 'output_message' | 'user',
    message: string
}

const ChatApp: React.FC = () => {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [input, setInput] = useState<string>('');
    const [messages, setMessages] = useState<Message[]>([]);

    useEffect(() => {
        const webSocket = new WebSocket('ws://localhost:8003/llm/');
        webSocket.onmessage = (message) => {
            const message_curr: Message = JSON.parse(message.data);
            if (message_curr.reporter === 'output_message') {
                setMessages((messages_prev) => {
                    // If messages_prev is empty, simply add the new message.
                    if (messages_prev.length === 0) {
                        return [message_curr];
                    }

                    // Get the last message from the previous state.
                    const message_last = messages_prev[messages_prev.length - 1];

                    if (message_last.type === "question" || message_last.type === "full") {
                        return [...messages_prev.slice(), message_curr];
                    }

                    // If the last message is 'full', append the new message.
                    if (message_curr.type === "full") {
                        return [...messages_prev.slice(0, -1), message_curr];
                    }

                    // If the last message is not 'full', concatenate it with the new message.
                    return [
                        ...messages_prev.slice(0, -1), // all messages except the last
                        {
                            ...message_last,
                            message: message_last.message + message_curr.message,
                        },
                    ];
                });
            }
        };

        setWs(webSocket);

        // Clean up on unmount
        return () => webSocket.close();
    }, []);

    const sendMessage = (): void => {
        if (ws) {
            ws.send(input);

            setMessages(((messages_prev) => [...messages_prev, {
                type: 'question',
                reporter: 'user',
                message: input
            }]));

            setInput(''); // Clear the input after sending
        }
    };

    return (
        <div style={{ width: "40%", height: "100vh", margin: "0 auto", display: "flex", flexDirection: "column" }}>
            <AppBar position="static" sx={{
                // backgroundColor: "#",
                backgroundImage: 'linear-gradient(45deg, #2f3f48, #586770)',
                // 
                borderBottomLeftRadius: 2,
                borderBottomRightRadius: 2
            }}>
                <Toolbar>

                    <Typography variant="h5" color="inherit" noWrap>
                        Minima
                    </Typography>
                </Toolbar>
            </AppBar>
            <List
                sx={{
                    flexGrow: 1,
                    marginTop: 2,
                    height: 128,
                    border: "1px solid gray",
                    borderRadius: 2, // Optional: if you want rounded corners
                    padding: 0, // Optional: to make sure the border aligns tightly if you have padding
                    marginBottom: 2, // Keeps the bottom spacing
                    overflowY: 'auto', // Ensures that the list can scroll on overflow
                }}
            >
                {messages.map((msg, index) => {
                    let isUser = msg.reporter === "user";

                    return (
                        <ListItem key={index} sx={{
                            display: 'flex', // Enable flex properties
                            flexDirection: 'column', // Stack children vertically

                            ...(isUser ? {
                                alignItems: 'flex-end', // Align to the right for odd items (assuming they represent the other person)
                            } : {
                                alignItems: 'flex-start', // Align items to the start (left side for LTR languages)
                            })
                        }}>
                            <ListItemText primary={msg.message} sx={{
                                maxWidth: '60%', // Messages can take up to 60% of the List width
                                bgcolor: 'background.paper', // Use the theme's paper color for the bubble background
                                borderRadius: '16px', // Rounded corners for the bubble effect
                                padding: '8px 16px', // Padding inside the bubble
                                wordBreak: 'break-word', // Ensures text wraps and doesn't overflow
                                ...(isUser ? {
                                    textAlign: "right",
                                    color: "white",
                                    backgroundImage: 'linear-gradient(120deg, #1a62aa, #007bff)',
                                } : {
                                    color: "black",
                                    backgroundImage: 'linear-gradient(120deg, #abcbe8, #7bade0)',
                                })
                            }} />
                            {/* <Box >
                        </Box> */}
                        </ListItem>
                    )
                })}
            </List>
            <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
            >

                <TextField
                    label="Type your message here"
                    variant="outlined"
                    multiline={true}
                    rows={5}
                    fullWidth
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            sendMessage();
                        }
                    }}

                    InputLabelProps={{
                        style: { color: '#fff' }, // Set the color of the label text to white
                    }}
                    InputProps={{
                        style: { color: '#fff' }, // Set the color of the input text to white
                    }}

                    // If using the outlined variant, you can use this to style the notched outline
                    sx={{
                        marginBottom: 2,
                        '& .MuiOutlinedInput-root': {
                            '& fieldset': {
                                borderColor: 'lightgray', // Set the border color to white
                            },
                            '&:hover fieldset': {
                                borderColor: 'lightgray', // Set the border color to white on hover (optional)
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: 'lightgray', // Set the border color to white when focused
                            },
                        },
                    }}
                />
            </Box>
        </div >
    );
};

export default ChatApp;
