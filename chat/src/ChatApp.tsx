import React, { useState, useEffect } from 'react';
import {
    Layout,
    Typography,
    List as AntList,
    Input,
    ConfigProvider,
    Switch,
    theme,
    Button,
} from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import {ToastContainer, toast, Bounce} from 'react-toastify';

const { Header, Content, Footer } = Layout;
const { TextArea } = Input;
const { Link: AntLink, Paragraph, Title } = Typography;
const { defaultAlgorithm, darkAlgorithm } = theme;

interface Message {
    type: 'answer' | 'question' | 'full';
    reporter: 'output_message' | 'user';
    message: string;
    links: string[];
}

const ChatApp: React.FC = () => {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [input, setInput] = useState<string>('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [isDarkMode, setIsDarkMode] = useState(false);

    // Toggle light/dark theme
    const toggleTheme = () => setIsDarkMode((prev) => !prev);

    // WebSocket Setup
    useEffect(() => {
        const webSocket = new WebSocket('ws://localhost:8003/llm/');

        webSocket.onmessage = (event) => {
            const message_curr: Message = JSON.parse(event.data);

            if (message_curr.reporter === 'output_message') {
                setMessages((messages_prev) => {
                    if (messages_prev.length === 0) return [message_curr];
                    const last = messages_prev[messages_prev.length - 1];

                    // If last message is question or 'full', append new
                    if (last.type === 'question' || last.type === 'full') {
                        return [...messages_prev, message_curr];
                    }

                    // If incoming message is 'full', replace last message
                    if (message_curr.type === 'full') {
                        return [...messages_prev.slice(0, -1), message_curr];
                    }

                    // Otherwise, merge partial message
                    return [
                        ...messages_prev.slice(0, -1),
                        {
                            ...last,
                            message: last.message + message_curr.message,
                        },
                    ];
                });
            }
        };

        setWs(webSocket);
        return () => {
            webSocket.close();
        };
    }, []);

    // Send message
    const sendMessage = (): void => {
        try {
            if (ws && input.trim()) {
                ws.send(input);
                setMessages((prev) => [
                    ...prev,
                    {
                        type: 'question',
                        reporter: 'user',
                        message: input,
                        links: [],
                    },
                ]);
                setInput('');
            }
        } catch (e) {
            console.error(e);
        }
    };

    async function handleLinkClick(link: string) {
        await navigator.clipboard.writeText(link);
        toast('Link copied!', {
            position: "top-right",
            autoClose: 1000,
            hideProgressBar: true,
            closeOnClick: true,
            pauseOnHover: true,
            draggable: false,
            progress: undefined,
            theme: "light",
            transition: Bounce,
        });
    }

    return (
        <ConfigProvider
            theme={{
                algorithm: isDarkMode ? darkAlgorithm : defaultAlgorithm,
                token: {
                    borderRadius: 2,
                },
            }}
        >
            <Layout
                style={{
                    width: '100%',
                    height: '100vh',
                    margin: '0 auto',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                }}
            >
                {/* Header with Theme Toggle */}
                <Header
                    style={{
                        backgroundImage: isDarkMode
                            ? 'linear-gradient(45deg, #10161A, #394B59)' // Dark gradient
                            : 'linear-gradient(45deg, #2f3f48, #586770)', // Light gradient
                        borderBottomLeftRadius: 2,
                        borderBottomRightRadius: 2,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0 16px',
                    }}
                >
                    <Title level={4} style={{ margin: 0, color: 'white' }}>
                        Minima
                    </Title>
                    <Switch
                        checked={isDarkMode}
                        onChange={toggleTheme}
                        checkedChildren="Dark"
                        unCheckedChildren="Light"
                    />
                </Header>

                {/* Messages */}
                <Content style={{ padding: '16px', display: 'flex', flexDirection: 'column' }}>
                    <AntList
                        style={{
                            flexGrow: 1,
                            marginBottom: 16,
                            border: '1px solid #ccc',
                            borderRadius: 4,
                            overflowY: 'auto',
                            padding: '16px',
                        }}
                    >
                        {messages.map((msg, index) => {
                            const isUser = msg.reporter === 'user';
                            return (
                                <AntList.Item
                                    key={index}
                                    style={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: isUser ? 'flex-end' : 'flex-start',
                                        border: 'none',
                                    }}
                                >
                                    <div
                                        style={{
                                            maxWidth: '60%',
                                            borderRadius: 16,
                                            padding: '8px 16px',
                                            wordBreak: 'break-word',
                                            textAlign: isUser ? 'right' : 'left',
                                            backgroundImage: isUser
                                                ? 'linear-gradient(120deg, #1a62aa, #007bff)'
                                                : 'linear-gradient(120deg, #abcbe8, #7bade0)',
                                            color: isUser ? 'white' : 'black',
                                        }}
                                    >
                                        <Paragraph
                                            style={{
                                                margin: 0,
                                                color: 'inherit',
                                                fontSize: '1rem',
                                                fontWeight: 500,
                                                lineHeight: '1.4',
                                            }}
                                        >
                                            {msg.message}
                                        </Paragraph>

                                        {/* Links, if any */}
                                        {msg.links?.length > 0 && (
                                            <div style={{ marginTop: 4 }}>
                                                {msg.links.map((link, linkIndex) => (
                                                    <React.Fragment key={linkIndex}>
                                                        <br />
                                                        <AntLink
                                                            onClick={async () => {
                                                                await handleLinkClick(link)
                                                            }}
                                                            href={link}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            style={{
                                                                color: 'inherit',
                                                                textDecoration: 'underline',
                                                            }}
                                                        >
                                                            {link}
                                                        </AntLink>
                                                    </React.Fragment>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </AntList.Item>
                            );
                        })}
                    </AntList>
                </Content>

                {/* Footer with TextArea & Circular Arrow Button */}
                <Footer style={{ padding: '16px' }}>
                    <div style={{ position: 'relative', width: '100%' }}>
                        <TextArea
                            placeholder="Type your message here..."
                            rows={5}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onPressEnter={(e) => {
                                // Allow SHIFT+ENTER for multiline
                                if (!e.shiftKey) {
                                    e.preventDefault();
                                    sendMessage();
                                }
                            }}
                            style={{
                                width: '100%',
                                border: '1px solid #ccc',
                                borderRadius: 4,
                                resize: 'none',
                                paddingRight: 60, // Extra space so text won't overlap the button
                            }}
                        />
                        <Button
                            shape="circle"
                            icon={<ArrowRightOutlined />}
                            onClick={sendMessage}
                            style={{
                                position: 'absolute',
                                bottom: 8,
                                right: 8,
                                width: 40,
                                height: 40,
                                minWidth: 40,
                                borderRadius: '50%',
                                fontWeight: 'bold',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        />
                    </div>
                </Footer>
            </Layout>
        </ConfigProvider>
    );
};

export default ChatApp;