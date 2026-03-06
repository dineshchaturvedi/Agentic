from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, Generic, cast, Type, TypedDict, get_type_hints
from dataclasses import dataclass, field
from datetime import datetime
from unittest import result
import uuid
import copy

StateSchema = TypeVar("StateSchema")

class Step(Generic[StateSchema]):
    # Init is constructor in Python world.
    def __init__(self, step_id: str, logic: Callable[[StateSchema], Dict]):
        self.step_id = step_id
        self.logic = logic
    # __str__ (The "User" view): This is called when you use print(obj) or str(obj). It’s meant to be a friendly, readable summary.
    # __repr__ (The "Developer" view): This stands for "representation." 
    # __str__ is like obj.toString() in Java. It’s meant to be a friendly, readable summary.
    def __str__(self) -> str:
        return f"Step('{self.step_id}')"


    def __repr__(self) -> str:
        return self.__str__()

    def run(self, state: StateSchema, state_schema: Type[StateSchema]) -> StateSchema:
        result = self.logic(state)
        # Get expected fields from the TypedDict
        expected_fields = get_type_hints(state_schema)

        # Create new state with all fields from state_schema
        # Only copy fields that are defined in state_schema
        updated = {**state}
        for field, value in result.items():
            if field in expected_fields:
                updated[field] = value

        return cast(StateSchema, updated)

class EntryPoint(Step[StateSchema]):
    """Special step that marks the beginning of the workflow.
    Users should connect this step to their first business logic step."""
    def __init__(self):
        super().__init__("entry", lambda x: {})

class Termination(Step[StateSchema]):
    """Special step that marks the end of the workflow.
    Users should connect their final business logic step(s) to this step."""
    def __init__(self):
        super().__init__("termination", lambda x: {})

@dataclass
class Transition(Generic[StateSchema]):
    source: str
    targets: List[str]
    condition: Optional[Callable[[StateSchema], Union[str, List[str], Step[StateSchema], List[Step[StateSchema]]]]] = None

    def __str__(self) -> str:
        return f"Transition('{self.source}' -> {self.targets})"

    def __repr__(self) -> str:
        return self.__str__()

    def resolve(self, state: StateSchema) -> List[str]:
        if self.condition:
            result = self.condition(state)
            if isinstance(result, Step):
                return [result.step_id]
            elif isinstance(result, list) and all(isinstance(x, Step) for x in result):
                return [step.step_id for step in result]
            elif isinstance(result, str):
                return [result]
            return result
        return self.targets

@dataclass
class Snapshot(Generic[StateSchema]):
    """Represents a single state snapshot in time"""
    snapshot_id: str
    timestamp: datetime
    state_data: StateSchema
    state_schema: Type[StateSchema]
    step_id: str

    def __str__(self) -> str:
        return f"Snapshot('{self.snapshot_id}') @ [{self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')}]: {self.step_id}.State({self.state_data})"

    def __repr__(self) -> str:
        return self.__str__()

    @classmethod
    def create(cls, state_data: StateSchema, state_schema: Type[StateSchema],
               step_id: str) -> 'Snapshot[StateSchema]':
        return cls(
            snapshot_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            state_data=state_data,
            state_schema=state_schema,
            step_id=step_id,
        )

@dataclass
class Run(Generic[StateSchema]):
    """Represents a single execution run of the state machine"""
    run_id: str
    start_timestamp: datetime
    snapshots: List[Snapshot[StateSchema]] = field(default_factory=list)
    end_timestamp: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"Run('{self.run_id}')"

    def __str__(self) -> str:
        return f"Run('{self.run_id}')"

    @classmethod
    def create(cls) -> 'Run[StateSchema]':
        return cls(
            run_id=str(uuid.uuid4()),
            start_timestamp=datetime.now()
        )

    @property
    def metadata(self) -> Dict:
        return {
            'run_id': self.run_id,
            'start_timestamp': self.start_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
            'end_timestamp': self.end_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f") if self.end_timestamp else None,
            "snapshot_counts": len(self.snapshots)
        }

    def add_snapshot(self, snapshot: Snapshot[StateSchema]):
        """Add a new snapshot to this run"""
        self.snapshots.append(snapshot)

    def complete(self):
        """Mark this run as complete"""
        self.end_timestamp = datetime.now()

    def get_final_state(self) -> Optional[StateSchema]:
        """Get the final state of this run"""
        if not self.snapshots:
            return None
        return self.snapshots[-1].state_data

"""
    MISSION: The Orchestrator for Structured Workflows.
    
    This class acts as a 'Conveyor Belt' for data (the State). It manages:
    1. REGISTRATION: Keeping a toolbox of functional 'Steps' (Workstations).
    2. NAVIGATION: Defining the 'Transitions' (Paths/Rules) between those steps.
    3. EXECUTION: A central 'Run' loop that moves data from start to finish.
    4. OBSERVABILITY: Creating an immutable history (Snapshots) of every change.
    
    It uses Python Generics and Pydantic (StateSchema) to ensure that every 
    step in the workflow is speaking the same 'data language'.
"""
class StateMachine(Generic[StateSchema]):
    def __init__(self, 
                 state_schema: Type[StateSchema]):
        # The 'Blueprint': Stores the Pydantic model that defines allowed data fields
        self.state_schema = state_schema
        # The 'Toolbox': A dictionary mapping step_ids to their functional code objects
        self.steps: Dict[str, Step[StateSchema]] = {}
        # The 'Map': A dictionary mapping step_ids to the 'arrows' leading to next steps
        self.transitions: Dict[str, List[Transition[StateSchema]]] = {}
    # These methods are just for debugging. If you print(my_machine), instead of seeing a messy 
    # memory address like <__main__.StateMachine at 0x7f...>, you will see a clean message telling 
    # you which schema this machine is using
    def __str__(self) -> str:
        schema_keys = list(get_type_hints(self.state_schema).keys())
        return f"StateMachine(schema={schema_keys})"
    # __str__ (The "User" view): This is called when you use print(obj) or str(obj). It’s meant to be a friendly, readable summary.
    # __repr__ (The "Developer" view): This stands for "representation." It is called when you type the variable name in a Python 
    # console or look at it in a list. It is meant to be unambiguous.
    def __repr__(self) -> str:
        return self.__str__()
        
    def add_steps(self, steps: List[Step[StateSchema]]):
        """
        Registers a list of 'Worker' steps into the machine.
        Each step must have a unique 'step_id' which acts as its primary key.
        """
        for step in steps:
            self.steps[step.step_id] = step

    def connect(
        self,
        # The Union keyword means "Either/Or." This was designed for convenience. When you call workflow.connect(), 
        # the machine is happy to receive either the actual Step object (s1) or just its ID string ("input").
        source: Union[Step[StateSchema], 
                      str],
        targets: Union[Step[StateSchema], 
                       str, 
                       List[Union[Step[StateSchema], str]]
                       ],
                    #   Callable[[StateSchema] defines input to the function is a StateSchema object, 
                    # and the function returns either a string or a list of strings.    
        condition: Optional[Callable[[StateSchema], Union[str, List[str]]]] = None
    ):
        """
        Creates the 'arrows' on our flowchart.
        - source: Where the data is coming from.
        - targets: Where the data can go next.
        - condition: A function that looks at the State and picks the correct target ID.
        """
        # Normalize: Convert Step objects into their ID strings for internal mapping
        src_id = source.step_id if isinstance(source, Step) else source
        target_list = targets if isinstance(targets, list) else [targets]
        target_ids = [t.step_id if isinstance(t, Step) else t for t in target_list]
        # Build the Transition object that will handle the logic during the 'run'
        transition = Transition[StateSchema](source=src_id, targets=target_ids, condition=condition)
        if src_id not in self.transitions:
            self.transitions[src_id] = []
        self.transitions[src_id].append(transition)

    def run(self, state: StateSchema):
        """
        The Execution Engine. Drives the State through the workflow loop.
        """
        # 1. PRE-FLIGHT CHECK: Verify input data matches the expected Schema fields
        expected_fields = get_type_hints(self.state_schema)
        state_fields = set(state.keys())
        common_fields = state_fields.intersection(expected_fields)

        if not common_fields:
            raise ValueError(f"Initial state must have at least one field from the schema. Expected fields: {list(expected_fields.keys())}")
        # 2. FIND START: Ensure there is exactly one 'EntryPoint' to begin execution
        entry_points = [s for s in self.steps.values() if isinstance(s, EntryPoint)]
        if not entry_points:
            raise Exception("No EntryPoint step found in workflow")
        if len(entry_points) > 1:
            raise Exception("Multiple EntryPoint steps found in workflow")

        # 3. INITIALIZE RUN: Start the 'Flight Recorder' to track every change
        current_run = Run.create()

        current_step_id = entry_points[0].step_id
        # 4. MAIN LOOP: Iterate until we hit a 'Termination' step or have no more paths
        while current_step_id:
            step = self.steps[current_step_id]
           # Check for 'Termination' subclass - this is our exit condition
            if isinstance(step, Termination):
                print(f"[StateMachine] Terminating: {current_step_id}")
                break

            # EXECUTE STEP: Run the worker logic and update our local 'state' variable
            # This is where LLMs are called or data is processed
            state = step.run(state, self.state_schema)

            # LOGGING: Print current progress to the console
            if isinstance(step, EntryPoint):
                print(f"[StateMachine] Starting: {current_step_id}")
            else:
                print(f"[StateMachine] Executing step: {current_step_id}")

            # SNAPSHOT: Save a deep copy of the data. 
            # This ensures that even if 'state' is modified later, this record remains correct.
            snapshot = Snapshot.create(copy.deepcopy(state), self.state_schema, current_step_id)
            current_run.add_snapshot(snapshot)
            # 5. NAVIGATION: Resolve where to go next
            transitions = self.transitions.get(current_step_id, [])
            next_steps: List[str] = []

            for t in transitions:
                # Resolve: Execute the transition's 'condition' logic using the NEW state
                next_steps += t.resolve(state)

            if not next_steps:
                raise Exception(f"[StateMachine] No transitions found from step: {current_step_id}")
            # SAFETY GUARD: Ensure we aren't trying to do two things at once yet
            if len(next_steps) > 1:
                raise NotImplementedError("Parallel execution not implemented yet.")
            # Move the 'cursor' to the next step ID for the next loop iteration
            current_step_id = next_steps[0]
        # 6. FINISH: Mark the run as successful and return the full history object
        current_run.complete()
        return current_run
