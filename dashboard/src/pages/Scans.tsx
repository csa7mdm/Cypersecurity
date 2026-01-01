import React, { useState } from 'react';
import Sidebar from '../../components/layout/Sidebar';
import { Card, CardHeader, CardTitle, CardContent, Badge, Button, Input, Modal } from '../../components/ui';
import { Shield, Plus, Search, Filter, Download, Eye, Play, Pause, Trash2 } from 'lucide-react';
import { formatRelativeTime } from '../../utils/cn';
import toast from 'react-hot-toast';

interface Scan {
    id: string;
    target: string;
    status: 'completed' | 'running' | 'scheduled' | 'failed';
    severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
    findings: number;
    timestamp: Date;
    progress?: number;
    scanType: string;
}

const Scans: React.FC = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [selectedScan, setSelectedScan] = useState<Scan | null>(null);
    const [newScanTarget, setNewScanTarget] = useState('');
    const [selectedScanType, setSelectedScanType] = useState('Full Scan');

    // Mock data
    const scans: Scan[] = [
        { id: '1', target: 'api.example.com', status: 'completed', severity: 'critical', findings: 12, timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), scanType: 'Full Scan' },
        { id: '2', target: 'web.example.com', status: 'running', severity: 'info', findings: 0, timestamp: new Date(Date.now() - 10 * 60 * 1000), progress: 45, scanType: 'Quick Scan' },
        { id: '3', target: 'app.example.com', status: 'completed', severity: 'high', findings: 8, timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000), scanType: 'Full Scan' },
        { id: '4', target: 'admin.example.com', status: 'scheduled', severity: 'info', findings: 0, timestamp: new Date(Date.now() + 24 * 60 * 60 * 1000), scanType: 'Deep Scan' },
        { id: '5', target: 'staging.example.com', status: 'failed', severity: 'info', findings: 0, timestamp: new Date(Date.now() - 12 * 60 * 60 * 1000), scanType: 'Quick Scan' },
        { id: '6', target: 'legacy.example.com', status: 'completed', severity: 'medium', findings: 15, timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000), scanType: 'Full Scan' },
    ];

    const filteredScans = scans.filter((scan) => {
        const matchesSearch = scan.target.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStatus = statusFilter === 'all' || scan.status === statusFilter;
        return matchesSearch && matchesStatus;
    });

    const getStatusBadge = (status: string) => {
        const badges = {
            completed: <Badge variant="success" size="sm">Completed</Badge>,
            running: <Badge variant="info" size="sm">Running</Badge>,
            scheduled: <Badge variant="warning" size="sm">Scheduled</Badge>,
            failed: <Badge variant="critical" size="sm">Failed</Badge>,
        };
        return badges[status as keyof typeof badges] || <Badge variant="default" size="sm">{status}</Badge>;
    };

    const handleCreateScan = () => {
        toast.success(`Scan started for ${newScanTarget}`);
        setIsCreateModalOpen(false);
        setNewScanTarget('');
    };

    return (
        <Sidebar>
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Security Scans</h1>
                        <p className="mt-1 text-gray-600 dark:text-gray-400">Manage and monitor your security scans</p>
                    </div>
                    <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setIsCreateModalOpen(true)}>
                        New Scan
                    </Button>
                </div>

                <Card variant="outlined">
                    <CardContent className="p-4">
                        <div className="flex flex-col md:flex-row gap-4">
                            <div className="flex-1">
                                <Input placeholder="Search by target..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} icon={<Search className="h-4 w-4" />} />
                            </div>
                            <div className="flex gap-2">
                                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="h-10 px-3 py-2 text-sm border rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500">
                                    <option value="all">All Status</option>
                                    <option value="completed">Completed</option>
                                    <option value="running">Running</option>
                                    <option value="scheduled">Scheduled</option>
                                    <option value="failed">Failed</option>
                                </select>
                                <Button variant="outline" size="md" icon={<Filter className="h-4 w-4" />}>Filters</Button>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card variant="outlined">
                    <CardContent className="p-0">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead><tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Target</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Type</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Findings</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Time</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Actions</th>
                                </tr></thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-800">
                                    {filteredScans.map((scan) => (
                                        <tr key={scan.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2">
                                                    <Shield className="h-4 w-4 text-gray-400" />
                                                    <div>
                                                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{scan.target}</div>
                                                        {scan.status === 'running' && scan.progress && (
                                                            <div className="mt-1 w-32">
                                                                <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                                                    <div className="h-full bg-primary-600 transition-all" style={{ width: `${scan.progress}%` }} />
                                                                </div>
                                                                <span className="text-xs text-gray-500">{scan.progress}%</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">{scan.scanType}</td>
                                            <td className="px-6 py-4 whitespace-nowrap">{getStatusBadge(scan.status)}</td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                {scan.findings > 0 ? <Badge variant={scan.severity} size="sm">{scan.findings} findings</Badge> : <span className="text-sm text-gray-500">-</span>}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatRelativeTime(scan.timestamp)}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    {scan.status === 'completed' && (<><button onClick={() => setSelectedScan(scan)} className="text-primary-600 hover:text-primary-700"><Eye className="h-4 w-4" /></button>
                                                        <button className="text-gray-600 hover:text-gray-700 dark:text-gray-400"><Download className="h-4 w-4" /></button></>)}
                                                    {scan.status === 'running' && <button className="text-gray-600 hover:text-gray-700"><Pause className="h-4 w-4" /></button>}
                                                    <button className="text-critical-600 hover:text-critical-700"><Trash2 className="h-4 w-4" /></button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {filteredScans.length === 0 && (<div className="text-center py-12"><Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" /><p className="text-gray-500">No scans found</p></div>)}
                    </CardContent>
                </Card>
            </div>

            <Modal isOpen={isCreateModalOpen} onClose={() => setIsCreateModalOpen(false)} title="Create New Scan" description="Configure and start a new security scan" size="lg">
                <div className="space-y-4">
                    <Input label="Target URL/IP" placeholder="example.com or 192.168.1.1" value={newScanTarget} onChange={(e) => setNewScanTarget(e.target.value)} icon={<Shield className="h-4 w-4" />} />
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Scan Type</label>
                        <div className="grid grid-cols-3 gap-2">
                            {['Quick Scan', 'Full Scan', 'Deep Scan'].map((type) => (
                                <button key={type} onClick={() => setSelectedScanType(type)} className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${selectedScanType === type ? 'bg-primary-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-primary-600 hover:text-white'}`}>
                                    {type}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="flex gap-2 justify-end pt-4">
                        <Button variant="outline" onClick={() => setIsCreateModalOpen(false)}>Cancel</Button>
                        <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={handleCreateScan} disabled={!newScanTarget}>Start Scan</Button>
                    </div>
                </div>
            </Modal>

            {selectedScan && (
                <Modal isOpen={!!selectedScan} onClose={() => setSelectedScan(null)} title={`Scan Details: ${selectedScan.target}`} size="xl">
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div><p className="text-sm text-gray-500">Status</p><p className="mt-1">{getStatusBadge(selectedScan.status)}</p></div>
                            <div><p className="text-sm text-gray-500">Findings</p><p className="mt-1"><Badge variant={selectedScan.severity}>{selectedScan.findings} vulnerabilities</Badge></p></div>
                        </div>
                        <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                            <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Top Findings</h4>
                            <div className="space-y-2">
                                {[1, 2, 3].map((i) => (
                                    <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-md">
                                        <Badge variant="critical" size="sm">Critical</Badge>
                                        <div className="flex-1">
                                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">SQL Injection Vulnerability</p>
                                            <p className="text-xs text-gray-500 mt-1">/api/users endpoint is vulnerable to SQL injection attacks</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </Modal>
            )}
        </Sidebar>
    );
};

export default Scans;
