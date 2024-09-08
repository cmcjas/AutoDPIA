'use client'

import { Button, TextField, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Box } from "@mui/material";
import { useRef, useEffect, useState } from 'react'
import axios from 'axios';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import { styled } from '@mui/material/styles';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';


const VisuallyHiddenInput = styled('input')({
    clip: 'rect(0 0 0 0)',
    clipPath: 'inset(50%)',
    height: 1,
    overflow: 'hidden',
    position: 'absolute',
    bottom: 0,
    left: 0,
    whiteSpace: 'nowrap',
    width: 1,
  });

interface TempProps {
    token: string | null;
}

const Template: React.FC<TempProps> = ({ token }) => {

    const [templates, setTemplates] = useState<{ userID: number, tempName: string, tempData : string}[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<string>('');
    const [error, setError] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [message, setMessage] = useState<string>('');

    const [open, setOpen] = useState(false);
    const [name, setName] = useState('');
    const [taskID, setTaskID] = useState<string>('');

    const chatParent = useRef<HTMLUListElement>(null)
    useEffect(() => {
        const domNode = chatParent.current
    })

    useEffect(() => {
        const fetchTemplates = async () => {
            try {
                const res = await axios.get('http://localhost:8080/get_templates', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
                });
                setTemplates(res.data);
            } catch (err) {
                setError(error);
            }
        };
        fetchTemplates();
    }, [error, open, token, processing]);

    const handleSelectChange = (event: SelectChangeEvent<unknown>) => {
        setMessage('');
        setSelectedTemplate(event.target.value as string);
    };


    const selectedTemplateData = templates.find(template => template.tempName === selectedTemplate)?.tempData??'';
    const selectedTempUserID = templates.find(template => template.tempName === selectedTemplate)?.userID??'';

    console.log(selectedTempUserID);

    interface Prompt {
        content: string;
        from: {"Step": string, "Section": string};
    }
    
    let templateData: Record<string, Record<string, Prompt>> = {};
    templateData = {} as Record<string, Record<string, Prompt>>;

    const [editableData, setEditableData] = useState(templateData);
    
    // Parse the JSON string to a JavaScript object
    if (selectedTemplateData === '') {
    } else {
        templateData = JSON.parse(selectedTemplateData);
    }
    // upload file for template extraction
    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        setMessage('');
        let File
        if (event.target.files && event.target.files[0]) {
          File = event.target.files[0]
        }

        if (!File) {
          alert('Please select a file first.');
          return;
        }

        const formData = new FormData();
        formData.append('File', File);
        formData.append('Mode', 'template');

        try {
          setProcessing(true);
          const res = await axios.post('http://localhost:8080/upload_doc', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
              'Authorization': `Bearer ${token}`
            }
          });

            if (res) {
                const resStart = await axios.post('http://localhost:8080/start_task',  
                    {
                        fileName: res.data['filename'],
                        taskName: 'extract_template',
                    },
                    {
                    headers : {
                        'Authorization': `Bearer ${token}`
                    }
                });

                setTaskID(resStart.data['task_id']);

                const result = await axios.get('http://localhost:8080/get_task_result',
                    {
                        params: {
                            taskID: resStart.data['task_id'],
                            taskName: 'extract_template'
                        },
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    }
                );

                setMessage(result.data['result']);
                setProcessing(false);
                setSelectedTemplate(res.data.tempName);

            } else {
                console.error('Failed to upload file.');
            }

          event.target.value = ''; // clear the input after uploading

        } catch (error) {
          console.error('Error uploading file', error);
        }
        
    };
    // select from existing templates
    const selectTempData = async () => {
        try {
            const res = await axios.post('http://localhost:8080/select_template', 
            {
                tempName: selectedTemplate,
                tempData: editableData
            },
            {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

        } catch (error) {
            console.error('Error:', error);
        }
    };

    useEffect(() => {
        setEditableData(templateData);
        selectTempData();
    }, [selectedTemplateData]);

    useEffect(() => {
        selectTempData();
    }, [editableData]);

    console.log(selectedTemplate, selectedTempUserID);

    // Add a new part to a step
    const handleAddPart = (step: string, title: string) => {
        // Create a copy of the current editableData
        const updatedData = { ...editableData };
    
        // Create an array of titles, sorted to maintain order
        const titles = Object.keys(updatedData[step]);
        const index = titles.indexOf(title);

        // Create a unique title for the new part
        let newTitleIndex = 1;
        let newTitle = `New Title ${newTitleIndex}`;
        while (titles.includes(newTitle)) {
            newTitleIndex++;
            newTitle = `New Title ${newTitleIndex}`;
        }

        // Insert the new part immediately after the current title
        const newTitles = [
            ...titles.slice(0, index + 1),
            newTitle,
            ...titles.slice(index + 1),
        ];

        // Create a new sections object with the new title inserted
        const newSections: Record<string, Prompt> = {};
        newTitles.forEach((title) => {
            newSections[title] = updatedData[step][title] || '';
        });

        // Set the default prompt value for the new title
        newSections[newTitle] = { content: '', from: {"Step": "", "Section": ""} };

        // Update the step with the new sections
        updatedData[step] = newSections;
    
        // Update the state with the new data
        setEditableData(updatedData);
    };
    // Delete a part from a step
    const handleDeletePart = (step: string, title: string) => {
        // Create a copy of the current editableData
        const updatedData = { ...editableData };

        const titles = Object.keys(updatedData[step]);

        if (titles.length > 1) {
            // Delete the specified title
            delete updatedData[step][title];
        }

        // Update the state with the new data
        setEditableData(updatedData);
    };

    // Add a new step to the template
    const handleAddStep = (step: string) => {
        // Create a copy of the current editableData
        const updatedData = { ...editableData };
    
        // Parse the step number from the current step string
        const stepMatch = step.match(/Step\s(\d+)/);
        const currentStepNumber = stepMatch ? parseInt(stepMatch[1], 10) : NaN;
    
        // Create a new step to add
        const newStepNumber = isNaN(currentStepNumber) ? 'NaN' : currentStepNumber + 1;
    
        // Get all step keys
        const stepKeys = Object.keys(updatedData);
    
        // Insert the new step and shift subsequent steps
        const newUpdatedData: Record<string, Record<string, Prompt>> = {};
        let stepInserted = false;
    
        for (let i = 0; i < stepKeys.length; i++) {
            const oldStepMatch = stepKeys[i].match(/(Step\s\d+)(.*)/);
            if (oldStepMatch) {
                const oldStepNumber = parseInt(oldStepMatch[1].replace('Step ', ''), 10);
                const suffix = oldStepMatch[2];
    
                if (oldStepNumber === currentStepNumber && !stepInserted) {
                    // Insert the new step right after the current step
                    newUpdatedData[`Step ${oldStepNumber}${suffix}`] = updatedData[stepKeys[i]];
                    newUpdatedData[`Step ${newStepNumber} - `] = { 'Role': { content: '', from: {"Step": "", "Section": ""} }} ;
                    stepInserted = true;
                } else if (oldStepNumber > currentStepNumber) {
                    // Shift the subsequent steps
                    newUpdatedData[`Step ${oldStepNumber + 1}${suffix}`] = updatedData[stepKeys[i]];
                } else {
                    newUpdatedData[stepKeys[i]] = updatedData[stepKeys[i]];
                }
            } else {
                // Preserve non-standard step names
                newUpdatedData[stepKeys[i]] = updatedData[stepKeys[i]];
                if (stepKeys[i] === step && !stepInserted) {
                    // Insert the new step after the non-standard step
                    newUpdatedData[`Step ${newStepNumber}`] = { 'Role': { content: '', from: {"Step": "", "Section": ""} } };
                    stepInserted = true;
                }
            }
        }
    
        // If the new step was not inserted (in case the current step number is the highest or non-standard), add it at the end
        if (!stepInserted) {
            newUpdatedData[`Step ${newStepNumber}`] = { 'Role': { content: '', from: {"Step": "", "Section": ""} } };
        }
    
        // Update the state with the new data
        setEditableData(newUpdatedData);
    };

    // Delete a step from the template
    const handleDeleteStep = (step: string) => {
        // Create a copy of the current editableData
        const updatedData = { ...editableData };
    
        // Check if there is only one step left
        if (Object.keys(updatedData).length === 1) {
            return; // Do not delete if there is only one step left
        }
    
        // Delete the specified step
        delete updatedData[step];
    
        // Separate non-standard steps from standard 'Step X' steps
        const nonStandardSteps: Record<string, Record<string, Prompt>> = {};
        const standardSteps: Record<string, Record<string, Prompt>> = {};
        const originalOrder: string[] = Object.keys(editableData);
    
        Object.keys(updatedData).forEach((key) => {
            if (key.startsWith('Step ')) {
                standardSteps[key] = updatedData[key];
            } else {
                nonStandardSteps[key] = updatedData[key];
            }
        });
    
        // Reorder the remaining standard 'Step X' steps while keeping the suffix
        const reorderedSteps: Record<string, Record<string, Prompt>> = {};
        let mainStepCounter = 1;
        let subStepCounters: Record<number, number> = {};
    
        Object.keys(standardSteps).forEach((key) => {
            const match = key.match(/(Step\s\d+)(\.\d+)?(.*)/);
            if (match) {
                const mainStepNumber = parseInt(match[1].replace('Step ', ''), 10);
                const subStepNumber = match[2] ? parseInt(match[2].replace('.', ''), 10) : null;
                const suffix = match[3];
    
                if (subStepNumber === null) {
                    // This is a main step
                    reorderedSteps[`Step ${mainStepCounter}${suffix}`] = standardSteps[key];
                    subStepCounters[mainStepCounter] = 1; // Initialize sub-step counter for this main step
                    mainStepCounter++;
                } else {
                    // This is a sub-step
                    const parentStepNumber = mainStepCounter - 1; // Attach to the last main step
                    reorderedSteps[`Step ${parentStepNumber}.${subStepCounters[parentStepNumber]}${suffix}`] = standardSteps[key];
                    subStepCounters[parentStepNumber]++;
                }
            }
        });
    
        // Merge reordered steps and non-standard steps back into the original order
        const finalData: Record<string, Record<string, Prompt>> = {};
    
        originalOrder.forEach((key) => {
            if (nonStandardSteps[key]) {
                finalData[key] = nonStandardSteps[key];
            } else {
                const reorderedKey = Object.keys(reorderedSteps).find((rk) => reorderedSteps[rk] === updatedData[key]);
                if (reorderedKey) {
                    finalData[reorderedKey] = reorderedSteps[reorderedKey];
                }
            }
        });
    
        // Update the state with the new data
        setEditableData(finalData);
    };
    
    const [openTitle, setOpenTitle] = useState(false);
    const [currentStep, setCurrentStep] = useState<string | null>(null);
    const [currentTitle, setCurrentTitle] = useState('');
    const [newTitle, setNewTitle] = useState('');

    const [openStep, setOpenStep] = useState(false);
    const [newStep, setNewStep] = useState('');

    // Open the dialog and set the current step and title
    const handleOpenTitle = (step: string, title: string) => {
        setCurrentStep(step);
        setCurrentTitle(title);
        setNewTitle(title);
        setOpenTitle(true);
      };
    // Close the dialog and reset the current step and title
    const handleCloseTitle = () => {
    setOpenTitle(false);
    setCurrentStep(null);
    setCurrentTitle('');
    setNewTitle('');
    };
    // Submit the new title and update the data
    const handleOpenStep = (step: string) => {
        setOpenStep(true);
        setCurrentStep(step);
        setNewStep(step);
    }
    // Close the dialog and reset the current step
    const handleCloseStep = () => {
        setOpenStep(false);
        setCurrentStep(null);
        setNewStep('');
    }
    // submit a new title for the part
    const handleTitleSubmit = () => {
    if (currentStep && currentTitle) {
        setEditableData(prevData => {
        const updatedData = { ...prevData };
        const stepData = updatedData[currentStep];
        const newSection = JSON.stringify(stepData).split(`"${currentTitle}":`).join(`"${newTitle}":`)
        updatedData[currentStep] = JSON.parse(newSection);
        
        return updatedData;
        });
    }
    handleCloseTitle();
    };
    
    // Submit a new title for the step
    const handleStepSubmit = () => {
        if (currentStep) {
            setEditableData(prevData => {
                const updatedData = { ...prevData };
                const newStepSection = JSON.stringify(updatedData).split(`"${currentStep}":`).join(`"${newStep}":`);
                return JSON.parse(newStepSection);
            });

        }
        handleCloseStep();
    }
    // change prompt content
    const handlePromptChange = (step: string, title: string, newPrompt: Prompt) => {
        setEditableData(prevData => {
            const newData = { ...prevData };
            newData[step][title] = newPrompt;
            return newData;
        });
    };

    const handleClickOpen = () => {
        setMessage('');
        setOpen(true);
      };
    
      const handleClose = () => {
        setOpen(false);
        setError(false);
      };
    
      const handleSave = async () => {
        if (name.trim() === '') {
          setError(true);
          return;
        }

        try {
            const res = await axios.post('http://localhost:8080/save_template', { tempName: name }, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
            });
        
            if (res) {
            // handle success
            handleClose();
            setMessage('Template saved successfully.');
            } 
        } catch (error) {
            console.error('Error:', error);
            setMessage('Name already exists.');
        }

      };
     // delete a template
      const handleDelete = async () => {
        setError(true);
        const res = await axios.post('http://localhost:8080/delete_template', selectedTemplate, {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
            },
        });
        if (res) {
            setError(false);
        }
      }

      const cancelExtract = async () => {
        setProcessing(false);
        if (taskID) {
            const cancel = await axios.post('http://localhost:8080/cancel_task', { taskID: taskID },
                {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                }
            );
        }

      }

    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">

            <header className="p-4 border-b w-full h-16 bg-gradient-to-r from-purple-500 to-pink-500">
                <h1 className="text-3xl font-bold">TEMPLATE</h1>
            </header>

            <Box bgcolor="#ededed" p={0.5} borderRadius={1}>
            <Box className="p-3" bgcolor="#ededed">
                <h1 className="text-1xl font-bold">Choose a Template</h1>
                <Select value={selectedTemplate} label="Template" onChange={handleSelectChange}>
                    <MenuItem value="">None...</MenuItem>
                    {templates.map(template => (
                    <MenuItem key={template.tempName} value={template.tempName}>
                        {template.tempName}
                    </MenuItem>
                    ))}
                </Select>

                <Button
                    component="label"
                    variant="contained"
                    color="success"
                    tabIndex={-1}
                    startIcon={<CloudUploadIcon />}
                    style={{marginLeft: '20px'}}
                    disabled={processing}
                >
                    Extract
                    <VisuallyHiddenInput type="file" onChange={handleFileChange} accept=".txt,.docx,.pdf" />
                    {processing && (
                        <img src='/loading-gif.gif' alt="GIF" style={{ marginLeft:'20px', width:'30px', height:'30px', marginRight: '15px'}}/>
                    )}
                </Button>
                {processing && (
                    <Button variant="outlined" color="secondary" style={{marginLeft: '15px'}} onClick={() => cancelExtract()}>Cancel</Button>
                )}
                <p>{message}</p>
            </Box>
            </Box>
            <section className="p-4 flex-1 overflow-auto" ref={chatParent}>

                {selectedTemplate && selectedTemplateData && (
                    <div>
                    {Object.entries(editableData).map(([step, sections], stepIndex) => (
                    <div key={step}>
                        <Box bgcolor="#e0e0e0" p={3} borderRadius={4} style={{ marginTop: '20px' }}>
                        <Button
                            variant="contained"
                            onClick={() => handleOpenStep(step)}
                            fullWidth
                        >
                            {step}
                        </Button>
                        <div style={{marginTop:"5px"}}>
                        <Button variant="outlined" onClick={() => handleAddStep(step)}>Add Step</Button>
                        <Button variant="outlined" onClick={() => handleDeleteStep(step)}>Delete Step</Button>
                        </div>
                        {Object.entries(sections).map(([title, prompt], sectionIndex) => (
                        <div key={title} style={{ marginBottom: '1rem' }}>
                                <Button
                                    variant="outlined"
                                    onClick={() => handleOpenTitle(step, title)}
                                    fullWidth
                                    style={{ marginBottom: '0.5rem', marginTop: '0.5rem' }}
                                >
                                    {title}
                                </Button>
                                <TextField
                                    label="Prompt"
                                    value={prompt.content}
                                    variant="outlined"
                                    onChange={(e) => handlePromptChange(step, title, { ...prompt, content: e.target.value })}
                                    fullWidth
                                    multiline
                                />
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: "5px" }}>
                                <div>
                                <Button variant="outlined" onClick={() => handleAddPart(step, title)}>Add Part</Button>
                                <Button variant="outlined" onClick={() => handleDeletePart(step, title)}>Delete Part</Button>
                                </div>
                            {!(stepIndex === 0 && sectionIndex === 0) && (
                                <div>
                                <span style={{ marginRight: '1rem' }}>Input From:</span> 
                                <TextField
                                    label="Step"
                                    value={prompt.from["Step"]}
                                    variant="outlined"
                                    size="small"
                                    onChange={(e) => handlePromptChange(step, title, { ...prompt, from: {"Step": e.target.value, "Section": prompt.from["Section"]} })}
                                />
                                <TextField
                                    label="Section"
                                    value={prompt.from["Section"]}
                                    variant="outlined"
                                    size="small"
                                    disabled={!prompt.from["Step"]}
                                    onChange={(e) => handlePromptChange(step, title, { ...prompt, from: {"Step": prompt.from["Step"], "Section": e.target.value} })}
                                />
                                </div>
                            )}
                            </div>
                        </div>
                        ))}
                        </Box>

                        <Dialog open={openTitle} onClose={handleCloseTitle}>
                                <DialogTitle>Enter a new Title:</DialogTitle>
                                <DialogContent>
                                <TextField
                                    autoFocus
                                    margin="dense"
                                    type="text"
                                    fullWidth
                                    value={newTitle}
                                    onChange={(e) => setNewTitle(e.target.value)}
                                />
                                </DialogContent>
                                <DialogActions>
                                <Button onClick={handleCloseTitle} color="primary">
                                    Cancel
                                </Button>
                                <Button onClick={handleTitleSubmit} color="primary">
                                    Submit
                                </Button>
                                </DialogActions>
                        </Dialog>

                        <Dialog open={openStep} onClose={handleCloseStep}>
                                <DialogTitle>Enter a new Step:</DialogTitle>
                                <DialogContent>
                                <TextField
                                    autoFocus
                                    margin="dense"
                                    type="text"
                                    fullWidth
                                    value={newStep}
                                    onChange={(e) => setNewStep(e.target.value)}
                                />
                                </DialogContent>
                                <DialogActions>
                                <Button onClick={handleCloseStep} color="primary">
                                    Cancel
                                </Button>
                                <Button onClick={handleStepSubmit} color="primary">
                                    Submit
                                </Button>
                                </DialogActions>
                        </Dialog>

                        <Dialog open={open} onClose={handleClose}>
                            <DialogTitle>Enter a Name</DialogTitle>
                            <DialogContent>
                            <TextField
                                autoFocus
                                margin="dense"
                                label="Template Name"
                                fullWidth
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                error={error}
                                helperText={error ? "Name cannot be empty" : ""}
                            />
                            </DialogContent>
                            <DialogActions>
                            <Button onClick={handleClose} color="secondary">
                                Cancel
                            </Button>
                            <Button onClick={handleSave} color="primary">
                                Save
                            </Button>
                            </DialogActions>
                            <p>{message}</p>
                        </Dialog>
                    </div>
                    ))}
                </div>
                )}
            {selectedTemplate && selectedTemplateData && (
            <div style={{marginTop:'15px'}}>
            <Button variant="contained" color="success" onClick={handleClickOpen}>
                Save
            </Button>
                {selectedTempUserID !== 0 && (
                <Button variant="outlined" onClick={handleDelete} color="secondary" style={{marginLeft: '10px'}}>
                    Delete
                </Button>
                )}
            </div>
            )}
            </section>
        </main>
    )
}

export default Template;