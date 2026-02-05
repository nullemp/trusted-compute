import React, { useState } from 'react';
import { Form, Input, Select, Button, Card, message, Tabs } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import client from '../api/client';

const { TextArea } = Input;
const { Option } = Select;

function CreateTask({ projectId }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [modelType, setModelType] = useState('sql');

  const handleSubmit = async (values) => {
    if (!projectId) {
      message.warning('请先选择项目');
      return;
    }

    try {
      setLoading(true);
      const taskData = {
        ...values,
        model_type: modelType,
        created_by: `user_${Date.now()}`,
        output_config: {
          masking_rules: {
            id: 'hash',
            value: 'generalize',
          },
        },
      };

      await client.post(`/api/projects/${projectId}/tasks`, taskData);
      message.success('计算任务创建成功');
      form.resetFields();
    } catch (error) {
      message.error('任务创建失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const sqlExample = `-- SQL计算示例
SELECT 
    category,
    COUNT(*) as count,
    AVG(value) as avg_value
FROM data_table
WHERE value > {{threshold}}
GROUP BY category
ORDER BY avg_value DESC;`;

  const pythonExample = `# Python计算示例
import pandas as pd
import numpy as np

# 模拟数据（实际数据来自各参与方）
data = pd.DataFrame({
    'id': [1, 2, 3, 4],
    'value': [100, 200, 150, 300],
    'category': ['A', 'B', 'A', 'C']
})

# 计算逻辑
result = data.groupby('category').agg({
    'value': ['mean', 'sum', 'count']
}).reset_index()

result.columns = ['category', 'mean_value', 'sum_value', 'count']
result = result.to_dict('records')`;

  return (
    <Card title={<><PlayCircleOutlined /> 创建计算任务</>}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
      >
        <Form.Item
          name="name"
          label="任务名称"
          rules={[{ required: true, message: '请输入任务名称' }]}
        >
          <Input placeholder="例如：数据分析任务" />
        </Form.Item>

        <Form.Item
          name="description"
          label="任务描述"
        >
          <TextArea rows={2} placeholder="描述任务的目标和计算逻辑" />
        </Form.Item>

        <Form.Item label="计算模型类型">
          <Select
            value={modelType}
            onChange={setModelType}
            style={{ width: 200 }}
          >
            <Option value="sql">SQL查询</Option>
            <Option value="python">Python脚本</Option>
          </Select>
        </Form.Item>

        <Form.Item
          name="model_code"
          label={`${modelType === 'sql' ? 'SQL' : 'Python'} 代码`}
          rules={[{ required: true, message: '请输入计算代码' }]}
        >
          <TextArea
            rows={10}
            placeholder={modelType === 'sql' ? sqlExample : pythonExample}
          />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>
            创建任务
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

export default CreateTask;
