
import { useEffect, useState } from 'react';
import axios from 'axios';


interface MetricProps {
    token: string | null;
}

const Metric: React.FC<MetricProps> = ({ token }) => {

    const [metrics, setMetrics] = useState({
        cpu: 0,
        gpu: 0,
        vram: 0,
        ram: 0,
        total_ram: 0,
        total_vram: 0,
        gpu_usage: 0,
        shared_vram: 0,
      });

    useEffect(() => {
        const fetchMetrics = async () => {
            const response = await axios.get('http://localhost:8080/usage_metric',
            {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            }
            );
            setMetrics(response.data);
        };
        // Fetch metrics immediately on component mount
        fetchMetrics();
        // Set up interval to fetch metrics every second
        const interval = setInterval(fetchMetrics, 1000);
        // Clean up interval on component unmount
        return () => clearInterval(interval);
    }, []);

    return (
        <div>
            <h1 className="text-1xl font-bold ">Powered By HP EDGE</h1>
            <p>CPU Usage: {metrics.cpu} %</p>
            <p>RAM Usage: {metrics.ram}/{metrics.total_ram} MB</p>
            <p>GPU Usage: {metrics.gpu} %</p>
            <p>VRAM Usage: {metrics.vram}/{metrics.total_vram} MB</p>
            <p>Shared VRAM: {metrics.shared_vram} MB</p>
        </div>
    );
}

export default Metric;