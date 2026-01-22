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
    Tag,
    Popconfirm,
    notification,
} from 'antd';
import { ArrowRightOutlined, UploadOutlined, InboxOutlined, LoadingOutlined, DeleteOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, MessageOutlined } from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd';

const { Header, Content, Footer, Sider } = Layout;
const { TextArea } = Input;
const { Link: AntLink, Paragraph, Title } = Typography;
const { defaultAlgorithm, darkAlgorithm } = theme;

interface Message {
    type: 'answer' | 'question' | 'full' | 'processing';
    reporter: 'output_message' | 'user';
    message: string;
    links: string[];
}

interface IndexedFile {
    path: string;
    status: 'uploaded' | 'indexing' | 'indexed' | 'failed';
    indexing_time_seconds: number | null;
    last_updated: number;
}

const ChatApp: React.FC = () => {
    const [ws, setWs] = useState<WebSocket | null>(null);
    const [input, setInput] = useState<string>('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [isDarkMode, setIsDarkMode] = useState(true);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const [fileList, setFileList] = useState<UploadFile[]>([]);
    const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
    const [isUploading, setIsUploading] = useState(false);
    const [indexedFiles, setIndexedFiles] = useState<IndexedFile[]>([]);
    const [isLoadingFiles, setIsLoadingFiles] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [userId, setUserId] = useState<string>('default_user');
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
        const webSocket = new WebSocket(`ws://localhost:8003/llm/?user_id=${userId}`);

        webSocket.onmessage = (event) => {
            const message_curr: Message = JSON.parse(event.data);

            if (message_curr.reporter === 'output_message') {
                // Remove typing indicator when we get first response
                setIsTyping(false);

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
    }, [userId]);

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
                setIsTyping(true); // Show typing indicator
            }
        } catch (e) {
            console.error(e);
        }
    };

    async function handleLinkClick(link: string) {
        await navigator.clipboard.writeText(link);
        notification.success({
            message: 'Link copied!',
            duration: 1,
            placement: 'topRight',
        });
    }

    // Handle file upload
    const handleUpload = async () => {
        if (fileList.length === 0) {
            notification.error({
                message: 'Please select files to upload',
                placement: 'topRight',
            });
            return;
        }

        setIsUploading(true);
        const formData = new FormData();

        // Append all files to FormData
        let filesAppended = 0;
        fileList.forEach((file) => {
            const fileObj = file.originFileObj || file;
            console.log('Processing file:', file.name, 'originFileObj:', file.originFileObj, 'fileObj:', fileObj);
            if (fileObj instanceof File || fileObj instanceof Blob) {
                formData.append('files', fileObj, file.name);
                filesAppended++;
                console.log('Appended file:', file.name);
            } else {
                console.error('File is not a File or Blob:', fileObj);
            }
        });

        console.log(`Total files appended to FormData: ${filesAppended}`);

        if (filesAppended === 0) {
            notification.error({
                message: 'No valid files to upload',
                placement: 'topRight',
            });
            setIsUploading(false);
            return;
        }

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
                    notification.success({
                        message: 'Upload successful',
                        description: `Successfully uploaded ${response.files?.length || fileList.length} file(s)!`,
                        placement: 'topRight',
                    });
                    setFileList([]);
                    setUploadProgress({});
                    setIsUploadModalOpen(false);
                    fetchIndexedFiles(); // Refresh file list after upload
                } else {
                    const errorData = xhr.responseText;
                    notification.error({
                        message: 'Upload failed',
                        description: errorData,
                        placement: 'topRight',
                        duration: 5,
                    });
                }
                setIsUploading(false);
            });

            xhr.addEventListener('error', () => {
                notification.error({
                    message: 'Upload failed',
                    description: 'Network error occurred',
                    placement: 'topRight',
                });
                setIsUploading(false);
            });

            xhr.open('POST', 'http://localhost:8001/files/add');
            xhr.setRequestHeader('X-User-Id', userId);
            xhr.send(formData);
        } catch (error) {
            console.error('Upload error:', error);
            notification.error({
                message: 'Failed to upload files',
                placement: 'topRight',
            });
            setIsUploading(false);
        }
    };

    // Fetch indexed files
    const fetchIndexedFiles = async () => {
        try{
            const response = await fetch('http://localhost:8001/files', {
                headers: {
                    'X-User-Id': userId
                }
            });
            const data = await response.json();
            const newFiles = data.files || [];

            // Only update state if data has changed
            setIndexedFiles((prevFiles) => {
                if (JSON.stringify(prevFiles) !== JSON.stringify(newFiles)) {
                    return newFiles;
                }
                return prevFiles; // Return same reference to prevent re-render
            });
        } catch (error) {
            console.error('Error fetching indexed files:', error);
        }
    };

    // Remove file from index
    const handleRemoveFile = async (filePath: string) => {
        try {
            const response = await fetch('http://localhost:8001/files/remove', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-User-Id': userId,
                },
                body: JSON.stringify({ files: [filePath] }),
            });

            if (response.ok) {
                notification.success({
                    message: 'File removed successfully',
                    placement: 'topRight',
                });
                fetchIndexedFiles(); // Refresh the list
            } else {
                const error = await response.json();
                notification.error({
                    message: 'Failed to remove file',
                    description: error.detail,
                    placement: 'topRight',
                });
            }
        } catch (error) {
            console.error('Error removing file:', error);
            notification.error({
                message: 'Failed to remove file',
                placement: 'topRight',
            });
        }
    };

    // Poll for file status updates
    useEffect(() => {
        setIsLoadingFiles(true);
        fetchIndexedFiles().finally(() => setIsLoadingFiles(false)); // Initial fetch with loading

        const interval = setInterval(() => {
            fetchIndexedFiles(); // Subsequent fetches without loading state
        }, 3000); // Poll every 3 seconds

        return () => clearInterval(interval);
    }, [userId]);

    // Get status tag
    const getStatusTag = (status: string) => {
        switch (status) {
            case 'indexed':
                return <Tag icon={<CheckCircleOutlined />} color="success">Indexed</Tag>;
            case 'indexing':
                return <Tag icon={<SyncOutlined spin />} color="processing">Indexing</Tag>;
            case 'uploaded':
                return <Tag icon={<ClockCircleOutlined />} color="default">Uploaded</Tag>;
            case 'failed':
                return <Tag icon={<CloseCircleOutlined />} color="error">Failed</Tag>;
            default:
                return <Tag>{status}</Tag>;
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
                notification.error({
                    message: `${file.name} is not a supported file type`,
                    placement: 'topRight',
                });
                return Upload.LIST_IGNORE;
            }

            // Create proper UploadFile object
            const uploadFile: UploadFile = {
                uid: file.uid,
                name: file.name,
                status: 'done',
                originFileObj: file,
            };

            setFileList((prev) => [...prev, uploadFile]);
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
                    borderRadius: 8,
                    colorPrimary: '#10a37f',
                },
            }}
        >
            <Layout
                style={{
                    width: '100%',
                    height: '100vh',
                    margin: '0 auto',
                    overflow: 'hidden',
                    background: isDarkMode ? '#212121' : '#ffffff',
                }}
            >
                {/* Main content area with sidebars and chat */}
                <Layout style={{ overflow: 'hidden' }}>
                    {/* Left Sidebar - Chat History */}
                    <Sider
                        width={260}
                        style={{
                            background: isDarkMode ? '#171717' : '#f7f7f8',
                            borderRight: `1px solid ${isDarkMode ? '#2d2d2d' : '#ececec'}`,
                            overflow: 'hidden',
                            display: 'flex',
                            flexDirection: 'column',
                        }}
                    >
                        {/* New Chat Button */}
                        <div style={{ padding: '12px' }}>
                            <Button
                                type="default"
                                icon={<MessageOutlined />}
                                block
                                style={{
                                    height: '44px',
                                    borderRadius: '8px',
                                    fontSize: '14px',
                                    fontWeight: 500,
                                    border: `1px solid ${isDarkMode ? '#2d2d2d' : '#d9d9d9'}`,
                                }}
                            >
                                New chat
                            </Button>
                        </div>

                        {/* Chat History List */}
                        <div
                            style={{
                                flex: 1,
                                overflowY: 'auto',
                                padding: '0 8px',
                            }}
                        >
                            <div
                                style={{
                                    padding: '10px 12px',
                                    margin: '4px 0',
                                    borderRadius: '8px',
                                    background: isDarkMode ? '#2d2d2d' : '#ececec',
                                    cursor: 'pointer',
                                    transition: 'background 0.2s',
                                }}
                            >
                                <Typography.Text
                                    style={{
                                        fontSize: '14px',
                                        fontWeight: 500,
                                    }}
                                >
                                    Current chat
                                </Typography.Text>
                            </div>
                        </div>

                        {/* Bottom section with theme toggle and upload */}
                        <div
                            style={{
                                borderTop: `1px solid ${isDarkMode ? '#2d2d2d' : '#ececec'}`,
                                padding: '12px',
                            }}
                        >
                            <Button
                                icon={<UploadOutlined />}
                                onClick={() => setIsUploadModalOpen(true)}
                                block
                                style={{
                                    marginBottom: '8px',
                                    height: '36px',
                                    borderRadius: '8px',
                                }}
                            >
                                Upload Files
                            </Button>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <Typography.Text type="secondary" style={{ fontSize: '13px' }}>
                                    Theme
                                </Typography.Text>
                                <Switch
                                    checked={isDarkMode}
                                    onChange={toggleTheme}
                                    size="small"
                                />
                            </div>
                        </div>
                    </Sider>

                    {/* Center - Chat Messages Area */}
                    <Content
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            overflow: 'hidden',
                            background: isDarkMode ? '#212121' : '#ffffff',
                        }}
                    >
                    {/* Messages Container */}
                    <div
                        style={{
                            flex: 1,
                            overflowY: 'auto',
                            padding: '20px',
                            width: '100%',
                        }}
                    >
                        {messages.map((msg, index) => {
                            const isUser = msg.reporter === 'user';
                            const isProcessing = msg.type === 'processing';
                            return (
                                <div
                                    key={index}
                                    style={{
                                        marginBottom: '24px',
                                        display: 'flex',
                                        gap: '8px',
                                        alignItems: 'flex-start',
                                        justifyContent: isUser ? 'flex-start' : 'flex-end',
                                        paddingLeft: '20px',
                                        paddingRight: '20px',
                                    }}
                                >
                                    {/* Avatar - show on left for user, right for assistant */}
                                    {isUser && (
                                        <div
                                            style={{
                                                width: '32px',
                                                height: '32px',
                                                borderRadius: '50%',
                                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                color: 'white',
                                                fontSize: '14px',
                                                fontWeight: 600,
                                                flexShrink: 0,
                                            }}
                                        >
                                            U
                                        </div>
                                    )}

                                    {/* Message Content */}
                                    <div style={{ minWidth: 0, maxWidth: '70%' }}>
                                        <div
                                            style={{
                                                fontSize: '15px',
                                                lineHeight: '1.7',
                                                color: isDarkMode ? '#ececec' : '#374151',
                                                wordBreak: 'break-word',
                                                whiteSpace: 'pre-wrap',
                                            }}
                                        >
                                            {isProcessing ? (
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
                                                    <span>{msg.message}</span>
                                                </div>
                                            ) : (
                                                <div>
                                                    {msg.message}
                                                </div>
                                            )}

                                            {/* Links */}
                                            {msg.links?.length > 0 && (
                                                <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                                    {msg.links.map((link, linkIndex) => (
                                                        <AntLink
                                                            key={linkIndex}
                                                            onClick={async () => {
                                                                await handleLinkClick(link)
                                                            }}
                                                            href={link}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            style={{
                                                                color: '#10a37f',
                                                                textDecoration: 'none',
                                                                fontSize: '14px',
                                                            }}
                                                        >
                                                            📎 {link}
                                                        </AntLink>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Avatar - show on right for assistant */}
                                    {!isUser && (
                                        <div
                                            style={{
                                                width: '32px',
                                                height: '32px',
                                                borderRadius: '50%',
                                                background: 'linear-gradient(135deg, #10a37f 0%, #0d8566 100%)',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                color: 'white',
                                                fontSize: '14px',
                                                fontWeight: 600,
                                                flexShrink: 0,
                                            }}
                                        >
                                            AI
                                        </div>
                                    )}
                                </div>
                            );
                        })}

                        {/* Typing Indicator */}
                        {isTyping && (
                            <div
                                style={{
                                    marginBottom: '24px',
                                    display: 'flex',
                                    gap: '8px',
                                    alignItems: 'flex-start',
                                    justifyContent: 'flex-end',
                                    paddingLeft: '20px',
                                    paddingRight: '20px',
                                }}
                            >
                                <div style={{ minWidth: 0, maxWidth: '70%' }}>
                                    <div
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px',
                                            color: isDarkMode ? '#999' : '#666',
                                        }}
                                    >
                                        <Spin indicator={<LoadingOutlined style={{ fontSize: 16 }} spin />} />
                                        <span>AI is typing...</span>
                                    </div>
                                </div>
                                <div
                                    style={{
                                        width: '32px',
                                        height: '32px',
                                        borderRadius: '50%',
                                        background: 'linear-gradient(135deg, #10a37f 0%, #0d8566 100%)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        color: 'white',
                                        fontSize: '14px',
                                        fontWeight: 600,
                                        flexShrink: 0,
                                    }}
                                >
                                    AI
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Footer with Input Area */}
                    <div
                        style={{
                            padding: '16px 20px 24px',
                            borderTop: `1px solid ${isDarkMode ? '#2d2d2d' : '#ececec'}`,
                            background: isDarkMode ? '#212121' : '#ffffff',
                        }}
                    >
                        <div
                            style={{
                                maxWidth: '900px',
                                margin: '0 auto',
                                position: 'relative',
                            }}
                        >
                            <div
                                style={{
                                    position: 'relative',
                                    background: isDarkMode ? '#2d2d2d' : '#f7f7f8',
                                    borderRadius: '12px',
                                    border: `1px solid ${isDarkMode ? '#3d3d3d' : '#d9d9d9'}`,
                                    boxShadow: isDarkMode
                                        ? '0 0 0 1px rgba(255,255,255,0.05)'
                                        : '0 0 0 1px rgba(0,0,0,0.05)',
                                    transition: 'all 0.2s',
                                    display: 'flex',
                                    alignItems: 'flex-end',
                                    padding: '12px',
                                    gap: '8px',
                                }}
                            >
                                <TextArea
                                    placeholder="Message..."
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onPressEnter={(e) => {
                                        if (!e.shiftKey) {
                                            e.preventDefault();
                                            sendMessage();
                                        }
                                    }}
                                    autoSize={{ minRows: 1, maxRows: 6 }}
                                    style={{
                                        border: 'none',
                                        background: 'transparent',
                                        resize: 'none',
                                        fontSize: '15px',
                                        lineHeight: '1.5',
                                        flex: 1,
                                        padding: 0,
                                    }}
                                />
                                <Button
                                    type="primary"
                                    shape="circle"
                                    icon={<ArrowRightOutlined />}
                                    onClick={sendMessage}
                                    disabled={!input.trim()}
                                    style={{
                                        width: '32px',
                                        height: '32px',
                                        minWidth: '32px',
                                        flexShrink: 0,
                                        background: input.trim() ? '#10a37f' : undefined,
                                        borderColor: input.trim() ? '#10a37f' : undefined,
                                    }}
                                />
                            </div>
                            <Typography.Text
                                type="secondary"
                                style={{
                                    fontSize: '12px',
                                    display: 'block',
                                    textAlign: 'center',
                                    marginTop: '12px',
                                }}
                            >
                                Powered by Qwen3
                            </Typography.Text>
                        </div>
                    </div>
                </Content>

                {/* Right Sidebar - File List */}
                <Sider
                    width={320}
                    style={{
                        background: isDarkMode ? '#171717' : '#f7f7f8',
                        borderLeft: `1px solid ${isDarkMode ? '#2d2d2d' : '#ececec'}`,
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column',
                    }}
                >
                    <div
                        style={{
                            padding: '16px',
                            borderBottom: `1px solid ${isDarkMode ? '#2d2d2d' : '#ececec'}`,
                        }}
                    >
                        <Title level={5} style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>
                            📁 Indexed Files
                        </Title>
                        <Typography.Text type="secondary" style={{ fontSize: '13px' }}>
                            {indexedFiles.length} {indexedFiles.length === 1 ? 'file' : 'files'}
                        </Typography.Text>
                    </div>

                    {/* File List */}
                    <div
                        style={{
                            flex: 1,
                            overflowY: 'auto',
                            padding: '12px',
                        }}
                    >
                        {isLoadingFiles ? (
                            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                                <Spin />
                                <div style={{ marginTop: '12px', color: '#999', fontSize: '13px' }}>
                                    Loading files...
                                </div>
                            </div>
                        ) : indexedFiles.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#999' }}>
                                <div style={{ fontSize: '40px', marginBottom: '12px' }}>📄</div>
                                <div style={{ fontSize: '14px' }}>No files indexed yet</div>
                                <div style={{ fontSize: '12px', marginTop: '8px' }}>
                                    Upload files to get started
                                </div>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {indexedFiles.map((file, idx) => (
                                    <div
                                        key={idx}
                                        style={{
                                            padding: '12px',
                                            background: isDarkMode ? '#2d2d2d' : 'white',
                                            borderRadius: '8px',
                                            border: `1px solid ${isDarkMode ? '#3d3d3d' : '#e5e7eb'}`,
                                            transition: 'all 0.2s',
                                            cursor: 'default',
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.borderColor = isDarkMode ? '#4d4d4d' : '#d1d5db';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.borderColor = isDarkMode ? '#3d3d3d' : '#e5e7eb';
                                        }}
                                    >
                                        <div
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'flex-start',
                                                marginBottom: '8px',
                                            }}
                                        >
                                            <Typography.Text
                                                strong
                                                style={{
                                                    fontSize: '13px',
                                                    flex: 1,
                                                    marginRight: '8px',
                                                    wordBreak: 'break-word',
                                                    lineHeight: '1.4',
                                                }}
                                                title={file.path}
                                            >
                                                {file.path.split('/').pop()}
                                            </Typography.Text>
                                            <Popconfirm
                                                title="Remove file?"
                                                description="This will remove the file from the index."
                                                onConfirm={() => handleRemoveFile(file.path)}
                                                okText="Remove"
                                                cancelText="Cancel"
                                                okButtonProps={{ danger: true }}
                                            >
                                                <Button
                                                    type="text"
                                                    danger
                                                    size="small"
                                                    icon={<DeleteOutlined />}
                                                    style={{
                                                        opacity: 0.6,
                                                    }}
                                                />
                                            </Popconfirm>
                                        </div>
                                        <div style={{ marginBottom: '6px' }}>
                                            {getStatusTag(file.status)}
                                        </div>
                                        {file.indexing_time_seconds && (
                                            <Typography.Text
                                                type="secondary"
                                                style={{ fontSize: '11px' }}
                                            >
                                                ⚡ {file.indexing_time_seconds}s
                                            </Typography.Text>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </Sider>
                </Layout>

                {/* File Upload Modal */}
                <Modal
                    title={
                        <div style={{ fontSize: '18px', fontWeight: 600 }}>
                            📤 Upload Files for Indexing
                        </div>
                    }
                    open={isUploadModalOpen}
                    onOk={handleUpload}
                    onCancel={() => {
                        if (!isUploading) {
                            setIsUploadModalOpen(false);
                            setFileList([]);
                            setUploadProgress({});
                        }
                    }}
                    okText="Upload Files"
                    cancelText="Cancel"
                    confirmLoading={isUploading}
                    width={600}
                    okButtonProps={{
                        disabled: fileList.length === 0 || isUploading,
                        style: {
                            background: '#10a37f',
                            borderColor: '#10a37f',
                        }
                    }}
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
        </ConfigProvider>
    );
};

export default ChatApp;