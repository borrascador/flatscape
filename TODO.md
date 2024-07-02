# TODO

- [x] Revise 'reverse' code to reduce memory usage
  - Instead of storing each slice in memory and replaying in reverse order, just assemble image in reverse order using adjusted pointers
  - Adjust the break out of loop logic
  - Use a new flag, --newreverse, until tested, then remove old --reverse flag and rename --newreverse to reverse
- [ ] Test threads and tasks and whether they improve performance
- [ ] Add logging from logging library
  - [x] First, convert all existing print statements to logging.info
  - [ ] Decide on logging convention
    - Per line: Show date, script, line number, logging level, and message
    - At the start, log location of script
    - At the end, log timing info
- [ ] Add option to write images to dated directory structure, e.g. output/walktest/2023/02/26/run1
  - [ ] Write logs to this directory
  - [ ] Write copy of python script used to this directory
- [ ] Add ability to set in and out frames
- [ ] Create video from stills
- [ ] Update process_frames to use numpy array updating