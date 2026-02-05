import React, { useState, useEffect } from 'react';
import { List, Card, Button, Tag, Typography, Input, Modal, message, Space, Collapse } from 'antd';
import { PlayCircleOutlined, FileTextOutlined, EyeOutlined } from '@ant-design/icons';
import client from '../api/client';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

function TaskList({ projectId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [executeModalVisible, setExecuteModalVisible] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [inputParams, setInputParams] = useState('{}');
  const [executing, setExecuting] = useState(false);
  const [results, setResults] = useState({});
  const [decryptedResults, setDecryptedResults] = useState({});
  const [decrypting, setDecrypting] = useState({});

  useEffect(() => {
    if (projectId) {
      fetchTasks();
    }
  }, [projectId]);

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await client.get(`/api/projects/${projectId}/tasks`);
      setTasks(response.data);
      
      // 获取每个任务的结果
      for (const task of response.data) {
        fetchTaskResults(task.id);
      }
    } catch (error) {
      message.error('获取任务列表失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTaskResults = async (taskId) => {
    try {
      const response = await client.get(`/api/tasks/${taskId}/results`);
      if (response.data.length > 0) {
        setResults(prev => ({
          ...prev,
          [taskId]: response.data,
        }));
      }
    } catch (error) {
      console.error('获取任务结果失败', error);
    }
  };

  const handleExecute = async () => {
    if (!selectedTask) return;

    try {
      setExecuting(true);
      let params;
      try {
        params = JSON.parse(inputParams);
      } catch (e) {
        message.error('输入参数格式错误，请输入有效的JSON');
        return;
      }

      const response = await client.post(
        `/api/tasks/${selectedTask.id}/execute`,
        { input_params: params }
      );

      message.success('任务执行成功！结果已加密保存');
      setExecuteModalVisible(false);
      fetchTaskResults(selectedTask.id);
    } catch (error) {
      message.error('任务执行失败');
      console.error(error);
    } finally {
      setExecuting(false);
    }
  };

  const openExecuteModal = (task) => {
    setSelectedTask(task);
    setInputParams('{"threshold": 100}');
    setExecuteModalVisible(true);
  };

  const handleDecryptResult = async (taskId, resultId) => {
    const key = `${taskId}-${resultId}`;
    if (decryptedResults[key]) {
      // 已解密，切换显示
      setDecryptedResults(prev => {
        const newState = { ...prev };
        delete newState[key];
        return newState;
      });
      return;
    }

    try {
      setDecrypting(prev => ({ ...prev, [key]: true }));
      const response = await client.get(`/api/tasks/${taskId}/results/${resultId}/decrypt`);
      setDecryptedResults(prev => ({ ...prev, [key]: response.data }));
      message.success('解密成功');
    } catch (error) {
      message.error('解密失败');
      console.error(error);
    } finally {
      setDecrypting(prev => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div>
      <Title level={3}>计算任务列表</Title>
      <List
        loading={loading}
        dataSource={tasks}
        renderItem={(task) => (
          <List.Item>
            <Card
              title={
                <Space>
                  <PlayCircleOutlined />
                  {task.name}
                </Space>
              }
              extra={
                <Space>
                  <Tag color={
                    task.status === 'completed' ? 'green' :
                    task.status === 'running' ? 'blue' :
                    task.status === 'failed' ? 'red' : 'default'
                  }>
                    {task.status}
                  </Tag>
                  <Tag>{task.model_type.toUpperCase()}</Tag>
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={() => openExecuteModal(task)}
                  >
                    执行任务
                  </Button>
                </Space>
              }
              style={{ width: '100%' }}
            >
              <Paragraph>{task.description || '暂无描述'}</Paragraph>
              <div style={{ marginTop: 12 }}>
                <Text type="secondary">
                  创建时间: {new Date(task.created_at).toLocaleString('zh-CN')}
                </Text>
              </div>
              
              {results[task.id] && results[task.id].length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <Title level={5}>执行结果:</Title>
                  {results[task.id].map((result) => {
                    const resultKey = `${task.id}-${result.id}`;
                    const decrypted = decryptedResults[resultKey];
                    const isDecrypting = decrypting[resultKey];
                    
                    return (
                      <Card
                        key={result.id}
                        size="small"
                        style={{ marginTop: 8 }}
                        extra={
                          <Button
                            size="small"
                            icon={<EyeOutlined />}
                            loading={isDecrypting}
                            onClick={() => handleDecryptResult(task.id, result.id)}
                          >
                            {decrypted ? '隐藏明文' : '查看明文'}
                          </Button>
                        }
                      >
                        {decrypted ? (
                          <div>
                            <Text strong style={{ fontSize: 12 }}>解密结果（已脱敏）:</Text>
                            <pre style={{ 
                              background: '#f5f5f5', 
                              padding: '8px', 
                              borderRadius: '4px',
                              fontSize: '12px',
                              maxHeight: '300px',
                              overflow: 'auto',
                              marginTop: '8px'
                            }}>
                              {JSON.stringify(decrypted.result, null, 2)}
                            </pre>
                          </div>
                        ) : (
                          <div>
                            <Text code style={{ fontSize: 12 }}>
                              密文: {result.encrypted_result.substring(0, 100)}...
                            </Text>
                          </div>
                        )}
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            执行时间: {result.execution_time}s | 
                            结果哈希: {result.result_hash?.substring(0, 16)}... | 
                            创建时间: {new Date(result.created_at).toLocaleString('zh-CN')}
                          </Text>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}
            </Card>
          </List.Item>
        )}
      />

      <Modal
        title="执行计算任务"
        open={executeModalVisible}
        onOk={handleExecute}
        onCancel={() => setExecuteModalVisible(false)}
        confirmLoading={executing}
        width={600}
      >
        {selectedTask && (
          <div>
            <Paragraph>
              <Text strong>任务:</Text> {selectedTask.name}
            </Paragraph>
            <Paragraph>
              <Text strong>模型类型:</Text> {selectedTask.model_type.toUpperCase()}
            </Paragraph>
            <div style={{ marginTop: 16 }}>
              <Text strong>输入参数 (JSON格式):</Text>
              <TextArea
                rows={6}
                value={inputParams}
                onChange={(e) => setInputParams(e.target.value)}
                placeholder='{"threshold": 100, "category": "A"}'
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default TaskList;
