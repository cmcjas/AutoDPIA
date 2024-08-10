'use client'

import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Box, Checkbox, TextField } from "@mui/material";
import { useEffect, useState } from 'react'
import axios from 'axios';
import { pdfjs, Document, Page } from 'react-pdf';
import PDFView from "./view";

import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import AssignmentIcon from '@mui/icons-material/Assignment';
import FolderIcon from '@mui/icons-material/Folder';
import Grid from '@mui/material/Grid';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
  ).toString();
  
import React from 'react';


interface DpiaProps {
  token: string | null;
  projectID: number;
  dpiaFileNames: string[];
  status: string;
}

export function Dpia(props: DpiaProps) {


    const [open, setOpen] = useState(false);
    const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
    const [selectedDocName, setSelectedDocName] = useState<string | null>('');
    const [generating, setGenerating] = useState<boolean>(false);

    const [dpias, setDpias] = useState<{ dpiaID: number; title: string; status: string }[]>([]);
    const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
    const [selectedNames, setSelectedNames] = useState<string[]>([]);
    const [selectedStatus, setSelectedStatus] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState<string>('');

    const [openGenerate, setOpenGenerate] = useState<boolean>(false);
    const [dpiaTitle, setDpiaTitle] = useState<string>('');

    const filteredDpias = dpias.filter(doc =>
        doc.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const projectID = props.projectID;
    const dpiaFileNames = props.dpiaFileNames;
    const token = props.token;

    const handleSelectAll = () => {
        if (selectedDocs.length === filteredDpias.length) {
          setSelectedDocs([]);
          setSelectedNames([]);
          setSelectedStatus([]);
        } else {
          setSelectedDocs(filteredDpias.map(doc => doc.dpiaID));
          setSelectedNames(filteredDpias.map(doc => doc.title));
          setSelectedStatus(filteredDpias.map(doc => doc.status));
        }
      };
      

    const handleGenerate = () => {
        setOpenGenerate(true);
    };

    const closeGenerate = () => {
        setOpenGenerate(false);
    };

    const handleDpiaStart = async () => {

        try {
            const init = await axios.post('http://localhost:8080/init_dpia', {
                projectID: projectID,
                title: dpiaTitle,
                fileName: dpiaFileNames
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            fetchDpias();
            const dpiaID = init.data.dpiaID;
            
            try {
                setOpenGenerate(false);
                setGenerating(true);
                const res = await axios.post('http://localhost:8080/generate_dpia', {
                    projectID: projectID,
                    title: dpiaTitle,
                    fileName: dpiaFileNames,
                    dpiaID: dpiaID
                }, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                fetchDpias();
                setGenerating(false);

            } catch (error) {
                console.error('Error starting DPIA:', error);
            }
        } catch (error) {
            console.error('Error starting DPIA:', error);
        }
    };
    

    useEffect(() => {
        fetchDpias();
    }, []);

    const fetchDpias = async () => {
        try {
            const res = await axios.get('http://localhost:8080/get_dpias', {params: { projectID: projectID }, 
                headers: {
                'Authorization': `Bearer ${token}`
            }
        });

            const status = res.data[0] && res.data[0].status;
            setDpias(res.data);
        } catch (error) {
            console.error('Error fetching documents:', error);
        }
    };

    const handleDpiaDelete = async () => {
        try {
            const res = await axios.post('http://localhost:8080/delete_dpias', selectedDocs, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
            });
            fetchDpias(); // Refresh the document list
            setSelectedDocs([]); // Clear the selected documents
            setGenerating(false);

        } catch (error) {
            console.error('Error deleting documents:', error);
        }
    };

    const handleView = async (dpiaID: number, title: string,) => {
        setOpen(true);
        setSelectedDocName(title);

        const res = await axios.get(`http://localhost:8080/view_dpias/${dpiaID}?projectID=${projectID}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            responseType: 'blob'
        });
        const url = window.URL.createObjectURL(new Blob([res.data]));
        setSelectedDoc(url);

    };

    const handleClose = () => {
        setOpen(false);
    };


    const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>, doc: { dpiaID: number; title: string; status: string }) => {
        if (event.target.checked) {
            setSelectedDocs([...selectedDocs, doc.dpiaID]);
            setSelectedNames([...selectedNames, doc.title]);
            setSelectedStatus([...selectedStatus, doc.status]);
        } else {
            setSelectedDocs(selectedDocs.filter(id => id !== doc.dpiaID));
            setSelectedNames(selectedNames.filter(name => name !== doc.title));
            setSelectedStatus(selectedStatus.filter(status => status !== doc.status));
        }
    };

    const handleDownload = async () => {
        for (let i = 0; i < selectedDocs.length; i++) {
            const dpiaID = selectedDocs[i];
            const dpiaName = selectedNames[i];
            const res = await axios.get(`http://localhost:8080/dpia_download/${dpiaID}?projectID=${projectID}`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
                responseType: 'blob',
            });
            console.log(dpiaName)
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `${dpiaName}.pdf`); // 
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };

    // search logics
    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
    };

    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">

            <div>
                <Button onClick={handleGenerate} variant="contained" color="success" disabled={generating}>Generate</Button>

                <Box bgcolor="#e0e0e0" p={3} borderRadius={4} style={{ marginTop: '20px' }}>
                <TextField
                    label="Search"
                    color="primary"
                    variant="outlined"
                    value={searchQuery}
                    onChange={handleSearchChange}
                    fullWidth
                    style={{ margin: '15px 0', }}
                />

                {filteredDpias.length > 0 && (
                <div>
                <Button onClick={handleSelectAll} variant="contained" color="secondary">
                    {selectedDocs.length === filteredDpias.length ? 'Deselect All' : 'Select All'}
                </Button>
                {selectedDocs.length > 0 && (
                <Button variant="contained" color="secondary" onClick={handleDpiaDelete} style={{ marginLeft: '20px' }}>
                    Delete
                </Button>
                )}
                {selectedDocs.length > 0 && selectedStatus.every(status => status == 'completed') && (
                <Button variant="contained" color="primary" onClick={handleDownload} style={{ marginLeft: '20px' }}>
                    Download
                </Button>
                )}
                </div>
                )}
                <Grid container spacing={2}>
                    <Grid item xs={12}>
                    
                    <List>
                        {filteredDpias.map(doc => (
                            <ListItem key={doc.dpiaID} className="flex justify-between items-center"
                                style={{ backgroundColor: '#ffffff', // White background for each item
                                    borderRadius: '4px', // Rounded corners for each item
                                    boxShadow: '0px 3px 6px rgba(0, 0, 0, 0.1)', // Light shadow to make items stand out
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    margin: '10px 0',
                                    alignItems: 'center', }}
                            >
                            <Checkbox
                                checked={selectedDocs.includes(doc.dpiaID) && selectedNames.includes(doc.title) && selectedStatus.includes(doc.status)}
                                onChange={(event) => handleCheckboxChange(event, doc)}
                            />
                                <ListItemIcon>
                                    <AssignmentIcon fontSize="large"/>
                                </ListItemIcon>
                                <ListItemText
                                    primary={doc.title}
                                />
                                {doc.status == 'working' && (
                                    <img src='/loading-gif.gif' alt="GIF" style={{width:'30px', height:'30px', marginRight: '15px'}}/>
                                )}
                                <div >
                                    {doc.status == 'working' ? (
                                        <h1>Processing, please wait...</h1>
                                    ) : (
                                        <Button onClick={() => handleView(doc.dpiaID, doc.title)} variant="contained" color="primary" style={{ marginRight: '10px' }}>View</Button>
                                    )}
                                </div>
                            </ListItem>
                        ))}
                    </List>
                    </Grid>
                </Grid>
                </Box>
            </div>

            <Dialog open={open} onClose={handleClose}  fullWidth maxWidth="lg">
                <DialogTitle>{selectedDocName}</DialogTitle>
                <DialogContent>
                    <PDFView fileLocation={selectedDoc} />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose} color="primary">
                        Close
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={openGenerate} onClose={closeGenerate}>
            <DialogTitle>Create DPIA</DialogTitle>
            <DialogContent>
                <TextField
                    autoFocus
                    margin="dense"
                    label="Project Title"
                    required
                    fullWidth
                    value={dpiaTitle}
                    onChange={(e) => setDpiaTitle(e.target.value)}
                />
            <List>
                <h1>Selected Files For DPIA: </h1>
                {dpiaFileNames.map((title, index) => (
                    <ListItem key={index}>
                        <ListItemIcon>
                            <FolderIcon />
                        </ListItemIcon>
                        <ListItemText primary={title} />
                    </ListItem>
                ))}
            </List>
            </DialogContent>
            <DialogActions>
                <Button onClick={closeGenerate}>Cancel</Button>
                <Button onClick={handleDpiaStart} color="primary">Start</Button>
            </DialogActions>
            </Dialog>        
        </main>
    );

}