'use client'

import { Button, TextField, Dialog, DialogActions, DialogContent, DialogTitle } from "@mui/material";
import { useRef, useEffect, useState } from 'react'
import axios from 'axios';

export function Template() {

    const [templates, setTemplates] = useState<{ tempName: string, tempData : string}[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<string>('');
    const [error, setError] = useState(false);

    useEffect(() => {
        fetch('http://localhost:8080/get_templates')
          .then(response => response.json())
          .then(data => setTemplates(data));
      }, [error]);

    const handleSelectChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedTemplate(event.target.value);
    };

    const selectedTemplateData = templates.find(template => template.tempName === selectedTemplate)?.tempData??'';
    let templateData: Record<string, Record<string, string>> = {};
    templateData = {} as Record<string, Record<string, string>>;

    const [editableData, setEditableData] = useState(templateData);
    
    // Parse the JSON string to a JavaScript object
    if (selectedTemplateData === '') {
        console.log('No template selected');
    } else {
        templateData = JSON.parse(selectedTemplateData);
    }

    console.log(templateData, editableData);

    const saveTemplateData = async () => {
        try {
            const res = await fetch('http://localhost:8080/select_template', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(editableData)
            });

            if (res.ok) {
                console.log('Template data saved successfully.');
            } else {
                console.error('Failed to save template data.');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    };

    useEffect(() => {
        setEditableData(templateData);
        saveTemplateData();
    }, [selectedTemplateData]);

    useEffect(() => {
        saveTemplateData();
    }, [editableData]);


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
        const newSections: Record<string, string> = {};
        newTitles.forEach((title) => {
            newSections[title] = updatedData[step][title] || '';
        });

        // Set the default prompt value for the new title
        newSections[newTitle] = '';

        // Update the step with the new sections
        updatedData[step] = newSections;
    
        // Update the state with the new data
        setEditableData(updatedData);
    };

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

    const handleAddStep = (step: string) => {
        // Create a copy of the current editableData
        const updatedData = { ...editableData };

        // Parse the step number from the current step string
        const currentStepNumber = parseInt(step.replace('Step ', ''), 10);

        // Create a new step to add
        const newStepNumber = currentStepNumber + 1;
        const newStep = `Step ${newStepNumber}`;

        // Create an array of step keys, sorted by step number
        const stepKeys = Object.keys(updatedData).sort((a, b) => {
            const stepA = parseInt(a.replace('step ', ''), 10);
            const stepB = parseInt(b.replace('step ', ''), 10);
            return stepA - stepB;
        });

        // Insert the new step and shift subsequent steps
        for (let i = stepKeys.length; i >= currentStepNumber; i--) {
            const stepKey = `Step ${i + 1}`;
            updatedData[stepKey] = updatedData[`Step ${i}`];
        }

        // Add the new step with a default title and empty prompt
        updatedData[newStep] = {
            'Role': ''
        };

        // Update the state with the new data
        setEditableData(updatedData);
    };

    const handleDeleteStep = (step: string) => {
        // Create a copy of the current editableData
        const updatedData = { ...editableData };

        // Check if there is only one step left
        if (Object.keys(updatedData).length === 1) {
            return; // Do not delete if there is only one step left
        }
    
        // Delete the specified step
        delete updatedData[step];
    
        // Reorder the remaining steps if necessary
        const reorderedData :  Record<string, Record<string, string>> = {};
        let stepCounter = 1;
        Object.keys(updatedData).sort().forEach((step) => {
            reorderedData[`Step ${stepCounter}`] = updatedData[step];
            stepCounter++;
        });
    
        // Update the state with the new data
        setEditableData(reorderedData);
    };

    

    const [openTitle, setOpenTitle] = useState(false);
    const [currentStep, setCurrentStep] = useState<string | null>(null);
    const [currentTitle, setCurrentTitle] = useState('');
    const [newTitle, setNewTitle] = useState('');

    const handleOpenTitle = (step: string, title: string, index: number) => {
        setCurrentStep(step);
        setCurrentTitle(title);
        setNewTitle(title);
        setOpenTitle(true);
      };
    
      const handleCloseTitle = () => {
        setOpenTitle(false);
        setCurrentStep(null);
        setCurrentTitle('');
        setNewTitle('');
      };
    
      const handleTitleSubmit = () => {
        if (currentStep && currentTitle) {
          setEditableData(prevData => {
            const updatedData = { ...prevData };
            const stepData = updatedData[currentStep];
            if (stepData && stepData[currentTitle]) {
              const sectionData = stepData[currentTitle];
              delete stepData[currentTitle];
              if (newTitle !== '') {
                stepData[newTitle] = sectionData;
              } else {
                stepData[currentTitle] = sectionData;
              }
            }
            return updatedData;
          });
        }
        handleCloseTitle();
      };

    const handlePromptChange = (step: string, title: string, newPrompt: string) => {
        setEditableData(prevData => {
            const newData = { ...prevData };
            newData[step][title] = newPrompt;
            return newData;
        });
    };



    const [open, setOpen] = useState(false);
    const [name, setName] = useState('');

    const handleClickOpen = () => {
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
    
        const response = await fetch('http://localhost:8080/save_template', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ tempName: name }),
        });
    
        if (response.ok) {
          // handle success
          handleClose();
        } else {
          // handle error
        }
      };


    return (
        <main className="flex flex-col w-full h-screen max-h-dvh bg-background">
            <header className="p-4 border-b w-full max-w-3xl mx-auto">
                <h1 className="text-2xl font-bold">Template</h1>
            </header>

            <div>
                <h1>Choose a Template</h1>
                <select value={selectedTemplate} onChange={handleSelectChange}>
                    <option value="">Select...</option>
                    {templates.map(template => (
                    <option key={template.tempName} value={template.tempName}>
                        {template.tempName}
                    </option>
                    ))}
                </select>

                {selectedTemplate && selectedTemplateData && (
                    <div>
                    {Object.entries(editableData).map(([step, sections]) => (
                    <div key={step}>
                        <h2>{step}</h2>
                        <Button variant="outlined" onClick={() => handleAddStep(step)}>Add Step</Button>
                        <Button variant="outlined" onClick={() => handleDeleteStep(step)}>Delete Step</Button>
                        {Object.entries(sections).map(([title, prompt], index) => (
                        <div key={title} style={{ marginBottom: '1rem' }}>
                                <Button
                                    variant="outlined"
                                    onClick={() => handleOpenTitle(step, title, index)}
                                    fullWidth
                                    style={{ marginBottom: '0.5rem' }}
                                >
                                    {title}
                                </Button>
                                <TextField
                                    label="Prompt"
                                    value={prompt}
                                    variant="outlined"
                                    onChange={(e) => handlePromptChange(step, title, e.target.value)}
                                    fullWidth
                                    multiline
                                />
                            <Button variant="outlined" onClick={() => handleAddPart(step, title)}>Add Part</Button>
                            <Button variant="outlined" onClick={() => handleDeletePart(step, title)}>Delete Part</Button>
                        </div>
                        ))}

                        <Dialog open={openTitle} onClose={handleCloseTitle}>
                                <DialogTitle>Enter a new title:</DialogTitle>
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
                            </Dialog>
                    </div>
                    ))}
                </div>
                )}
            </div>
            {selectedTemplate && selectedTemplateData && (
            <Button variant="contained" color="primary" onClick={handleClickOpen}>
                Save
            </Button>
            )}
        </main>
    )

}