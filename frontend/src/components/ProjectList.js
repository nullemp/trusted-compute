import React, { useState, useEffect } from 'react';
import { List, Card, Button, Tag, Typography, Space, message } from 'antd';
import { ProjectOutlined, UserOutlined } from '@ant-design/icons';
import client from '../api/client';

const { Title, Text } = Typography;

function ProjectList({ onSelectProject }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const response = await client.get('/api/projects');
      setProjects(response.data);
    } catch (error) {
      message.error('获取项目列表失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleJoinProject = async (projectId) => {
    try {
      const participantId = `user_${Date.now()}`;
      const participantName = `用户${Date.now() % 1000}`;
      
      await client.post(`/api/projects/${projectId}/join`, {
        participant_id: participantId,
        participant_name: participantName,
        data_resource: {
          type: 'sample_data',
          description: '示例数据资源',
        },
      });
      
      message.success('成功加入项目');
      fetchProjects();
    } catch (error) {
      message.error('加入项目失败');
      console.error(error);
    }
  };

  return (
    <div>
      <Title level={2}>项目列表</Title>
      <List
        loading={loading}
        grid={{ gutter: 16, column: 1 }}
        dataSource={projects}
        renderItem={(project) => (
          <List.Item>
            <Card
              title={
                <Space>
                  <ProjectOutlined />
                  {project.name}
                </Space>
              }
              extra={
                <Space>
                  <Tag color={project.status === 'active' ? 'green' : 'default'}>
                    {project.status}
                  </Tag>
                  <Button
                    type="primary"
                    onClick={() => onSelectProject(project)}
                  >
                    查看任务
                  </Button>
                  <Button onClick={() => handleJoinProject(project.id)}>
                    加入项目
                  </Button>
                </Space>
              }
              style={{ width: '100%' }}
            >
              <Text>{project.description || '暂无描述'}</Text>
              <div style={{ marginTop: 12 }}>
                <Text type="secondary">
                  创建者: {project.owner_id} | 创建时间:{' '}
                  {new Date(project.created_at).toLocaleString('zh-CN')}
                </Text>
              </div>
            </Card>
          </List.Item>
        )}
      />
    </div>
  );
}

export default ProjectList;
