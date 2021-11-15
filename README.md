# ASHP Sizing and Selection Tool

# Software
1.	Install Miniconda from https://docs.conda.io/en/latest/miniconda.html Use Windows installers.
2.	Install git from https://git-scm.com/

#  Configuration
1.	Open a git bash prompt (Start -> Git Bash)
* Clone this repository to your computer:
```
git clone https://github.com/canmet-energy/ASHP-Sizing-and-Selection-Tool
```
2.	Open a miniconda prompt (Start -> Anaconda Prompt (Miniconda3)).
* Change into the project folder (i.e. where you cloned this repository):
```
cd ASHP-Sizing-and-Selection-Tool
```
* Set up your python environment called “ASHPtool”:
```
conda env create --prefix ./env --file environment.yml
```
* Activate your conda environment:
```
conda activate <path_to_your_environment>
```
* Launch the Jupyter Notebook App:
```
jupyter notebook
```
