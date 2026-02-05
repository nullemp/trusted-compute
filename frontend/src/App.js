import React, { useState } from 'react';
import { Layout, Menu, Card, Typography } from 'antd';
import {
  ProjectOutlined,
  PlusOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import ProjectList from './components/ProjectList';
import CreateProject from './components/CreateProject';
import CreateTask from './components/CreateTask';
import TaskList from './components/TaskList';
import './App.css';

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

function App() {
  const [selectedMenu, setSelectedMenu] = useState('projects');
  const [selectedProject, setSelectedProject] = useState(null);

  const menuItems = [
    {
      key: 'projects',
      icon: <ProjectOutlined />,
      label: '项目管理',
    },
    {
      key: 'create-project',
      icon: <PlusOutlined />,
      label: '创建项目',
    },
  ];

  const renderContent = () => {
    switch (selectedMenu) {
      case 'projects':
        return (
          <ProjectList
            onSelectProject={(project) => {
              setSelectedProject(project);
              setSelectedMenu('project-tasks');
            }}
          />
        );
      case 'create-project':
        return <CreateProject onCreated={() => setSelectedMenu('projects')} />;
      case 'project-tasks':
        return (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Title level={3}>项目: {selectedProject?.name}</Title>
            </div>
            <Card style={{ marginBottom: 16 }}>
              <CreateTask projectId={selectedProject?.id} />
            </Card>
            <TaskList projectId={selectedProject?.id} />
          </div>
        );
      default:
        return <div>请选择功能</div>;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px' }}>
        <Title level={3} style={{ color: '#fff', margin: '16px 0' }}>
          可信模型计算平台
        </Title>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedMenu]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={({ key }) => setSelectedMenu(key)}
          />
        </Sider>
        <Content style={{ padding: '24px', background: '#f0f2f5' }}>
          {renderContent()}
        </Content>
      </Layout>
    </Layout>
  );
}

export default App;
