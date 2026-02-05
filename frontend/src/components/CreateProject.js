import React, { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { ProjectOutlined } from '@ant-design/icons';
import client from '../api/client';

const { TextArea } = Input;

function CreateProject({ onCreated }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values) => {
    try {
      setLoading(true);
      const projectData = {
        ...values,
        owner_id: `owner_${Date.now()}`,
        data_config: {
          required_fields: ['id', 'value'],
          data_types: ['integer', 'string'],
        },
      };

      await client.post('/api/projects', projectData);
      message.success('项目创建成功');
      form.resetFields();
      if (onCreated) {
        onCreated();
      }
    } catch (error) {
      message.error('项目创建失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title={<><ProjectOutlined /> 创建可信模型计算项目</>}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        style={{ maxWidth: 800 }}
      >
        <Form.Item
          name="name"
          label="项目名称"
          rules={[{ required: true, message: '请输入项目名称' }]}
        >
          <Input placeholder="例如：医疗数据分析项目" />
        </Form.Item>

        <Form.Item
          name="description"
          label="项目描述"
        >
          <TextArea
            rows={4}
            placeholder="描述项目的目标、数据要求等信息"
          />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>
            创建项目
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

export default CreateProject;
