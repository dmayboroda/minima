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
    Upload,
    Progress,
    Modal,
    Spin,
} from 'antd';
import { ArrowRightOutlined, UploadOutlined, InboxOutlined, LoadingOutlined } from '@ant-design/icons';
import {ToastContainer, toast, Bounce} from 'react-toastify';
import type { UploadProps, UploadFile } from 'antd';

const { Header, Content, Footer } = Layout;
const { TextArea } = Input;
const { Link: AntLink, Paragraph, Title } = Typography;
const { defaultAlgorithm, darkAlgorithm } = theme;

interface Message {
    type: 'answer' | 'question' | 'full' | 'processing';
    reporter: 'output_message' | 'user';
    message: string;
    links: string[];
}

const ChatApp: React.FC = () => {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [input, setInput] = useState<string>('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [isDarkMode, setIsDarkMode] = useState(false);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [fileList, setFileList] = useState<UploadFile[]>([]);
    const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
    const [isUploading, setIsUploading] = useState(false);
    const messagesEndRef = React.useRef<HTMLDivElement>(null);

    // Toggle light/dark theme
    const toggleTheme = () => setIsDarkMode((prev) => !prev);

    // Auto-scroll to latest message
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // WebSocket Setup
    useEffect(() => {
        const webSocket = new WebSocket('ws://localhost:8003/llm/');

        webSocket.onmessage = (event) => {
            const message_curr: Message = JSON.parse(event.data);

            if (message_curr.reporter === 'output_message') {
                setMessages((messages_prev) => {
                    if (messages_prev.length === 0) return [message_curr];
                    const last = messages_prev[messages_prev.length - 1];

                    // If incoming is processing message, append it
                    if (message_curr.type === 'processing') {
                        return [...messages_prev, message_curr];
                    }

                    // If last message is processing and we get an answer, replace it
                    if (last.type === 'processing' && message_curr.type === 'answer') {
                        return [...messages_prev.slice(0, -1), message_curr];
                    }

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

    // Handle file upload
    const handleUpload = async () => {
        if (fileList.length === 0) {
            toast.error('Please select files to upload');
            return;
        }

        setIsUploading(true);
        const formData = new FormData();

        fileList.forEach((file) => {
            if (file.originFileObj) {
                formData.append('files', file.originFileObj);
            }
        });

        try {
            const xhr = new XMLHttpRequest();

            // Track upload progress
            xhr.upload.addEventListener('progress', (event) => {
                if (event.lengthComputable) {
                    const percentComplete = Math.round((event.loaded / event.total) * 100);
                    setUploadProgress((prev) => ({ ...prev, overall: percentComplete }));
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    toast.success(`Successfully uploaded ${response.files?.length || fileList.length} file(s)!`, {
                        position: "top-right",
                        autoClose: 3000,
                    });
                    setFileList([]);
                    setUploadProgress({});
                    setIsUploadModalOpen(false);
                } else {
                    toast.error('Upload failed: ' + xhr.responseText, {
                        position: "top-right",
                        autoClose: 5000,
                    });
                }
                setIsUploading(false);
            });

            xhr.addEventListener('error', () => {
                toast.error('Upload failed due to network error');
                setIsUploading(false);
            });

            xhr.open('POST', 'http://localhost:8001/files/add');
            xhr.send(formData);
        } catch (error) {
            console.error('Upload error:', error);
            toast.error('Failed to upload files');
            setIsUploading(false);
        }
    };

    // Upload props for Ant Design Upload component
    const uploadProps: UploadProps = {
        multiple: true,
        fileList: fileList,
        beforeUpload: (file) => {
            const isSupportedType = [
                '.pdf', '.xls', '.xlsx', '.doc', '.docx',
                '.txt', '.md', '.csv', '.ppt', '.pptx'
            ].some(ext => file.name.toLowerCase().endsWith(ext));

            if (!isSupportedType) {
                toast.error(`${file.name} is not a supported file type`);
                return false;
            }

            setFileList((prev) => [...prev, file as UploadFile]);
            return false; // Prevent auto upload
        },
        onRemove: (file) => {
            setFileList((prev) => prev.filter((f) => f.uid !== file.uid));
        },
    };

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
                {/* Header with Theme Toggle and Upload Button */}
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
                        Running on Qwen3
                    </Title>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                        <Button
                            type="primary"
                            icon={<UploadOutlined />}
                            onClick={() => setIsUploadModalOpen(true)}
                        >
                            Upload Files
                        </Button>
                        <Switch
                            checked={isDarkMode}
                            onChange={toggleTheme}
                            checkedChildren="Dark"
                            unCheckedChildren="Light"
                        />
                    </div>
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
                            const isProcessing = msg.type === 'processing';
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
                                                : isProcessing
                                                ? 'linear-gradient(120deg, #f0f0f0, #e0e0e0)'
                                                : 'linear-gradient(120deg, #abcbe8, #7bade0)',
                                            color: isUser ? 'white' : isProcessing ? '#666' : 'black',
                                        }}
                                    >
                                        {isProcessing ? (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <Spin indicator={<LoadingOutlined style={{ fontSize: 18 }} spin />} />
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
                                            </div>
                                        ) : (
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
                                        )}

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
                        <div ref={messagesEndRef} />
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

                {/* File Upload Modal */}
                <Modal
                    title="Upload Files for Indexing"
                    open={isUploadModalOpen}
                    onOk={handleUpload}
                    onCancel={() => {
                        if (!isUploading) {
                            setIsUploadModalOpen(false);
                            setFileList([]);
                            setUploadProgress({});
                        }
                    }}
                    okText="Upload"
                    cancelText="Cancel"
                    confirmLoading={isUploading}
                    width={600}
                    okButtonProps={{ disabled: fileList.length === 0 || isUploading }}
                >
                    <div style={{ marginBottom: 16 }}>
                        <Upload.Dragger {...uploadProps}>
                            <p className="ant-upload-drag-icon">
                                <InboxOutlined />
                            </p>
                            <p className="ant-upload-text">Click or drag files to this area to upload</p>
                            <p className="ant-upload-hint">
                                Supported formats: PDF, Excel, Word, Text, Markdown, CSV, PowerPoint
                            </p>
                        </Upload.Dragger>
                    </div>

                    {/* Upload Progress */}
                    {isUploading && uploadProgress.overall !== undefined && (
                        <div style={{ marginTop: 16 }}>
                            <Progress percent={uploadProgress.overall} status="active" />
                            <p style={{ marginTop: 8, textAlign: 'center' }}>
                                Uploading files... {uploadProgress.overall}%
                            </p>
                        </div>
                    )}

                    {/* File List Summary */}
                    {fileList.length > 0 && !isUploading && (
                        <div style={{ marginTop: 16 }}>
                            <Typography.Text strong>
                                {fileList.length} file(s) selected
                            </Typography.Text>
                        </div>
                    )}
                </Modal>
            </Layout>
            <ToastContainer />
        </ConfigProvider>
    );
};

export default ChatApp;