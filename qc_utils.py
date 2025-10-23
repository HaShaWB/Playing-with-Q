"""
Qiskit 주피터 노트북 유틸리티
양자 회로를 실행하고 결과를 시각화하는 편의 함수들
"""
from qiskit import QuantumCircuit
from matplotlib import pyplot as plt
from qiskit_ibm_runtime import SamplerV2
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram
from qiskit.quantum_info import Statevector
from IPython.display import display
import warnings
warnings.filterwarnings('ignore')



# ==================== 내부 헬퍼 함수 ====================

def _display_circuit(qc: QuantumCircuit, style='mpl', title=None):
    """회로 시각화 (내부 함수)"""
    try:
        if style == 'mpl':
            fig = qc.draw('mpl', scale=0.5)
            if title:
                fig.suptitle(title)
            display(fig)
        elif style == 'text':
            if title:
                print(f"\n{title}:")
            print(qc.draw())
        elif style == 'latex':
            if title:
                print(f"\n{title}:")
            display(qc.draw('latex'))
        else:
            fig = qc.draw('mpl', scale=0.5)
            if title:
                fig.suptitle(title)
            display(fig)
    except Exception as e:
        print(f"회로 시각화 오류 (텍스트로 대체): {e}")
        print(qc.draw())


def _display_circuits_grid(circuits: list[QuantumCircuit], labels: list[str], style='mpl'):
    """여러 회로를 가로로 배치 (내부 함수)"""
    n_circuits = len(circuits)
    
    if style == 'mpl':
        fig, axes = plt.subplots(1, n_circuits, figsize=(4 * n_circuits, 3))
        if n_circuits == 1:
            axes = [axes]
        
        for idx, (circuit, label) in enumerate(zip(circuits, labels)):
            try:
                circuit.draw('mpl', ax=axes[idx], scale=0.5)
                axes[idx].set_title(label)
            except Exception as e:
                axes[idx].text(0.5, 0.5, f"오류: {e}", ha='center', va='center', fontsize=8)
        
        fig.tight_layout()
        display(fig)
        plt.close()
    else:
        # text나 latex는 세로로 표시
        for circuit, label in zip(circuits, labels):
            _display_circuit(circuit, style=style, title=label)


def _run_circuit(circuit: QuantumCircuit, backend, shots=1000):
    """회로 실행 (내부 함수)"""
    sampler = SamplerV2(backend)
    job = sampler.run([circuit], shots=shots)
    result = job.result()
    return result[0].data.meas.get_counts()


def _run_circuits_batch(circuits: list[QuantumCircuit], backend, shots=1000):
    """여러 회로 배치 실행 (내부 함수)"""
    sampler = SamplerV2(backend)
    job = sampler.run(circuits, shots=shots)
    results = job.result()
    return [pub_result.data.meas.get_counts() for pub_result in results]


def _get_ideal_counts(circuit: QuantumCircuit, shots=1000):
    """
    이론적 확률을 계산하여 샷 수에 맞게 counts 반환 (통계적 요동 없음)
    
    Statevector를 사용하여 정확한 이론적 확률을 계산한 후,
    샷 수에 비례하여 counts를 생성
    """
    # 측정이 없는 회로 복사
    qc_no_measure = circuit.copy()
    if qc_no_measure.cregs:
        # 측정 제거
        qc_no_measure = QuantumCircuit(circuit.num_qubits)
        for instruction in circuit.data:
            if instruction.operation.name != 'measure':
                qc_no_measure.append(instruction)
    
    # Statevector로 이론적 확률 계산
    statevector = Statevector(qc_no_measure)
    probabilities = statevector.probabilities_dict()
    
    # 확률을 counts로 변환 (반올림하여 정수로)
    ideal_counts = {}
    remaining_shots = shots
    
    # 확률이 높은 순서대로 정렬
    sorted_probs = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
    
    for i, (state, prob) in enumerate(sorted_probs):
        if i == len(sorted_probs) - 1:
            # 마지막 상태는 남은 샷 모두 할당 (반올림 오차 보정)
            ideal_counts[state] = remaining_shots
        else:
            count = round(prob * shots)
            ideal_counts[state] = count
            remaining_shots -= count
    
    # 0이 아닌 counts만 반환
    return {state: count for state, count in ideal_counts.items() if count > 0}


def _get_ideal_counts_batch(circuits: list[QuantumCircuit], shots=1000):
    """여러 회로의 이론적 counts를 계산 (내부 함수)"""
    return [_get_ideal_counts(circuit, shots) for circuit in circuits]


# ==================== 메인 함수 ====================

def run_and_visualize(qc: QuantumCircuit,
                      shots: int = 1000,
                      backend=None,
                      show_circuit: bool = True,
                      show_histogram: bool = True,
                      show_results: bool = True,
                      circuit_style: str = 'mpl',
                      compare_with_ideal: bool = True,
                      optimize_circuit: bool = True):
    """
    양자 회로를 실행하고 결과를 시각화한다.

    Args:
        qc (QuantumCircuit): 실행할 양자 회로 (측정이 없으면 자동으로 measure_all 추가).
        shots (int): 측정 샷 수. 기본값은 1000.
        backend (Backend, optional): 사용할 백엔드. None이면 AerSimulator를 사용한다.
        show_circuit (bool): 회로도를 표시할지 여부. 기본값은 True.
        show_histogram (bool): 결과 히스토그램을 표시할지 여부. 기본값은 True.
        show_results (bool): 측정 결과를 텍스트로 출력할지 여부. 기본값은 True.
        circuit_style (str): 회로도 스타일 ('mpl', 'text', 'latex'). 기본값은 'mpl'.
        compare_with_ideal (bool): 하드웨어 실행 시 시뮬레이터 결과도 함께 표시할지 여부. 기본값은 True.
        optimize_circuit (bool): 하드웨어 실행 시 회로 최적화(transpile) 여부. 기본값은 True.

    Returns:
        dict or tuple: 측정 결과 counts.
            compare_with_ideal=True이고 하드웨어 백엔드일 경우 (ideal_counts, hw_counts) 튜플을 반환한다.

    Examples:
        >>> qc = QuantumCircuit(2)
        >>> qc.h(0)
        >>> qc.cx(0, 1)
        >>> counts = run_and_visualize(qc)
    """
    
    # 회로 복사 (원본 수정 방지)
    circuit = qc.copy()
    
    # 측정이 없으면 자동 추가
    if not circuit.cregs:
        circuit.measure_all()
    
    # 백엔드 설정
    if backend is None:
        backend = AerSimulator()
    
    # 하드웨어 여부 체크
    from qiskit import transpile
    is_hardware = hasattr(backend, 'simulator') and not backend.simulator
    
    # 회로도 표시 (원본)
    if show_circuit:
        print("\n[ Quantum Circuit ]")
        _display_circuit(circuit, style=circuit_style)
    
    # 하드웨어인 경우 transpile
    hw_circuit = circuit
    if is_hardware and optimize_circuit:
        hw_circuit = transpile(circuit, backend=backend, optimization_level=3)
        
        # Transpile된 회로 표시
        if show_circuit and circuit_style == 'mpl':
            print("\n[ Transpiled Circuit (Basis Gates) ]")
            _display_circuit(hw_circuit, style=circuit_style)
    
    # 실행 및 결과
    if is_hardware and compare_with_ideal:
        # 이론적 확률과 하드웨어 결과 비교
        ideal_counts = _get_ideal_counts(circuit, shots)
        hw_counts = _run_circuit(hw_circuit, backend, shots)
        
        # 결과 출력 (비교)
        if show_results:
            print(f"\n[ Results Comparison ] shots={shots}")
            print("\n<Ideal (Simulator)>")
            for state, count in sorted(ideal_counts.items(), key=lambda x: x[1], reverse=True):
                probability = count / shots * 100
                print(f"|{state}⟩: {count:4d}회 ({probability:6.2f}%)")
            
            print(f"\n<Hardware ({backend.name})>")
            for state, count in sorted(hw_counts.items(), key=lambda x: x[1], reverse=True):
                probability = count / shots * 100
                print(f"|{state}⟩: {count:4d}회 ({probability:6.2f}%)")
        
        # 히스토그램 표시 (비교)
        if show_histogram:
            print("\n[ Histogram Comparison ]")
            fig, axes = plt.subplots(1, 2, figsize=(8, 3))
            
            # Ideal - x축 정렬
            sorted_ideal = dict(sorted(ideal_counts.items()))
            bars_ideal = axes[0].bar(sorted_ideal.keys(), sorted_ideal.values(), color='C0')
            axes[0].set_xlabel('State', fontsize=12)
            axes[0].set_ylabel('Count', fontsize=12)
            axes[0].set_title('Ideal (Simulator)')
            axes[0].set_ylim(0, shots * 1.2)
            axes[0].tick_params(axis='both', labelsize=11)
            # 막대 위에 비율 표시
            for bar in bars_ideal:
                height = bar.get_height()
                axes[0].text(bar.get_x() + bar.get_width()/2., height,
                           f'{height/shots*100:.1f}%',
                           ha='center', va='bottom', fontsize=9)
            
            # Hardware - x축 정렬
            sorted_hw = dict(sorted(hw_counts.items()))
            bars_hw = axes[1].bar(sorted_hw.keys(), sorted_hw.values(), color='C1')
            axes[1].set_xlabel('State', fontsize=12)
            axes[1].set_ylabel('Count', fontsize=12)
            axes[1].set_title(f'Hardware ({backend.name})')
            axes[1].set_ylim(0, shots * 1.2)
            axes[1].tick_params(axis='both', labelsize=11)
            # 막대 위에 비율 표시
            for bar in bars_hw:
                height = bar.get_height()
                axes[1].text(bar.get_x() + bar.get_width()/2., height,
                           f'{height/shots*100:.1f}%',
                           ha='center', va='bottom', fontsize=9)
            
            fig.tight_layout()
            display(fig)
            plt.close()
        
        return ideal_counts, hw_counts
    
    else:
        # 일반 실행 (시뮬레이터 또는 비교 안 함)
        counts = _run_circuit(hw_circuit, backend, shots)
        
        if show_results:
            backend_name = getattr(backend, 'name', 'Simulator')
            print(f"\n[ Results ] shots={shots}, states={len(counts)} ({backend_name})")
            for state, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                probability = count / shots * 100
                print(f"|{state}⟩: {count:4d}회 ({probability:6.2f}%)")
        
        # 히스토그램 표시
        if show_histogram:
            print("\n[ Histogram ]")
            fig, ax = plt.subplots(figsize=(5, 3))
            
            # x축 정렬
            sorted_counts = dict(sorted(counts.items()))
            bars = ax.bar(sorted_counts.keys(), sorted_counts.values(), color='C0')
            ax.set_xlabel('State', fontsize=12)
            ax.set_ylabel('Count', fontsize=12)
            ax.set_ylim(0, shots * 1.2)
            ax.tick_params(axis='both', labelsize=11)
            
            # 막대 위에 비율 표시
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height/shots*100:.1f}%',
                       ha='center', va='bottom', fontsize=9)
            
            fig.tight_layout()
            display(fig)
            plt.close()
        
        return counts


def compare_circuits(circuits: list[QuantumCircuit], 
                     labels=None, 
                     shots=1000, 
                     backend=None,
                     show_circuit=True, 
                     show_histogram=True, 
                     show_results=True,
                     circuit_style='mpl', 
                     compare_with_ideal=True):
    """
    여러 양자 회로의 결과를 비교합니다.
    
    Parameters
    ----------
    circuits : list of QuantumCircuit
        비교할 양자 회로들
    labels : list of str, optional
        각 회로의 레이블
    shots : int, default=1000
        측정 샷 수
    backend : Backend, optional
        사용할 백엔드
    show_circuit : bool, default=True
        회로도를 표시할지 여부
    show_histogram : bool, default=True
        결과 히스토그램을 표시할지 여부
    show_results : bool, default=True
        측정 결과를 텍스트로 출력할지 여부
    circuit_style : str, default='mpl'
        회로도 스타일 ('mpl', 'text', 'latex')
    compare_with_ideal : bool, default=True
        하드웨어 실행 시 시뮬레이터 결과도 함께 표시
    
    Returns
    -------
    list of dict or tuple of lists
        각 회로의 측정 결과 counts (compare_with_ideal=True이고 하드웨어면 (ideal_counts_list, hw_counts_list))
    
    Examples
    --------
    >>> qc1 = QuantumCircuit(1)
    >>> qc1.h(0)
    >>> qc2 = QuantumCircuit(1)
    >>> qc2.x(0)
    >>> compare_circuits([qc1, qc2], labels=['Hadamard', 'X gate'])
    """
    
    if backend is None:
        backend = AerSimulator()
    
    if labels is None:
        labels = [f"Circuit {i+1}" for i in range(len(circuits))]
    
    # 측정 추가
    from qiskit import transpile
    is_hardware = hasattr(backend, 'simulator') and not backend.simulator
    
    circuits_with_measurement = []
    for circuit in circuits:
        qc = circuit.copy()
        if not qc.cregs:
            qc.measure_all()
        circuits_with_measurement.append(qc)
    
    # 회로도 표시 (원본)
    if show_circuit:
        print("\n[ Quantum Circuits ]")
        _display_circuits_grid(circuits_with_measurement, labels, style=circuit_style)
    
    # 하드웨어인 경우 transpile
    hw_circuits = circuits_with_measurement
    if is_hardware:
        hw_circuits = [transpile(qc, backend=backend, optimization_level=3) 
                      for qc in circuits_with_measurement]
        
        # Transpile된 회로 표시
        if show_circuit and circuit_style == 'mpl':
            print("\n[ Transpiled Circuits (Basis Gates) ]")
            transpile_labels = [f"{label} (transpiled)" for label in labels]
            _display_circuits_grid(hw_circuits, transpile_labels, style=circuit_style)
    
    # 실행 및 결과
    if is_hardware and compare_with_ideal:
        # 이론적 확률과 하드웨어 결과 비교
        ideal_counts_list = _get_ideal_counts_batch(circuits_with_measurement, shots)
        hw_counts_list = _run_circuits_batch(hw_circuits, backend, shots)
        
        # 결과 출력 (비교)
        if show_results:
            print(f"\n[ Results Comparison ] shots={shots}")
            
            for i, label in enumerate(labels):
                print(f"\n{label}:")
                print("  <Ideal>", end="")
                for state, count in sorted(ideal_counts_list[i].items(), key=lambda x: x[1], reverse=True)[:3]:
                    probability = count / shots * 100
                    print(f"  |{state}⟩: {probability:5.1f}%", end="")
                
                print(f"\n  <HW>   ", end="")
                for state, count in sorted(hw_counts_list[i].items(), key=lambda x: x[1], reverse=True)[:3]:
                    probability = count / shots * 100
                    print(f"  |{state}⟩: {probability:5.1f}%", end="")
                print()
        
        # 히스토그램 표시 (비교)
        if show_histogram:
            print("\n[ Comparison Histogram ]")
            
            n_circuits = len(circuits)
            fig, axes = plt.subplots(2, n_circuits, figsize=(4 * n_circuits, 6))
            
            if n_circuits == 1:
                axes = axes.reshape(2, 1)
            
            for idx, label in enumerate(labels):
                # Ideal - x축 정렬
                sorted_ideal = dict(sorted(ideal_counts_list[idx].items()))
                bars_ideal = axes[0, idx].bar(sorted_ideal.keys(), sorted_ideal.values(), color='C0')
                axes[0, idx].set_xlabel('State', fontsize=12)
                axes[0, idx].set_ylabel('Count', fontsize=12)
                axes[0, idx].set_title(f'{label} (Ideal)')
                axes[0, idx].set_ylim(0, shots * 1.2)
                axes[0, idx].tick_params(axis='both', labelsize=11)
                # 막대 위에 비율 표시
                for bar in bars_ideal:
                    height = bar.get_height()
                    axes[0, idx].text(bar.get_x() + bar.get_width()/2., height,
                                    f'{height/shots*100:.1f}%',
                                    ha='center', va='bottom', fontsize=9)
                
                # Hardware - x축 정렬
                sorted_hw = dict(sorted(hw_counts_list[idx].items()))
                bars_hw = axes[1, idx].bar(sorted_hw.keys(), sorted_hw.values(), color='C1')
                axes[1, idx].set_xlabel('State', fontsize=12)
                axes[1, idx].set_ylabel('Count', fontsize=12)
                axes[1, idx].set_title(f'{label} (HW)')
                axes[1, idx].set_ylim(0, shots * 1.2)
                axes[1, idx].tick_params(axis='both', labelsize=11)
                # 막대 위에 비율 표시
                for bar in bars_hw:
                    height = bar.get_height()
                    axes[1, idx].text(bar.get_x() + bar.get_width()/2., height,
                                    f'{height/shots*100:.1f}%',
                                    ha='center', va='bottom', fontsize=9)
            
            fig.tight_layout()
            display(fig)
            plt.close()
        
        return ideal_counts_list, hw_counts_list
    
    else:
        # 일반 실행 (시뮬레이터 또는 비교 안 함)
        all_counts = _run_circuits_batch(hw_circuits, backend, shots)
        
        if show_results:
            backend_name = getattr(backend, 'name', 'Simulator')
            print(f"\n[ Results ] shots={shots} ({backend_name})")
            for i, (label, counts) in enumerate(zip(labels, all_counts)):
                print(f"\n{label}:")
                for state, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                    probability = count / shots * 100
                    print(f"  |{state}⟩: {count:4d}회 ({probability:6.2f}%)")
        
        # 히스토그램
        if show_histogram:
            print("\n[ Comparison Histogram ]")
            
            n_circuits = len(all_counts)
            fig, axes = plt.subplots(1, n_circuits, figsize=(4 * n_circuits, 3))
            
            if n_circuits == 1:
                axes = [axes]
            
            for idx, (counts, label) in enumerate(zip(all_counts, labels)):
                # x축 정렬
                sorted_counts = dict(sorted(counts.items()))
                bars = axes[idx].bar(sorted_counts.keys(), sorted_counts.values(), color=f'C{idx}')
                axes[idx].set_xlabel('State', fontsize=12)
                axes[idx].set_ylabel('Count', fontsize=12)
                axes[idx].set_title(label)
                axes[idx].set_ylim(0, shots * 1.2)
                axes[idx].tick_params(axis='both', labelsize=11)
                
                # 막대 위에 비율 표시
                for bar in bars:
                    height = bar.get_height()
                    axes[idx].text(bar.get_x() + bar.get_width()/2., height,
                                 f'{height/shots*100:.1f}%',
                                 ha='center', va='bottom', fontsize=9)
            
            fig.tight_layout()
            display(fig)
            plt.close()
        
        return all_counts


def quick_run(qc: QuantumCircuit, 
              shots=1000, 
              backend=None, 
              show_results=False,
              compare_with_ideal=False):
    """
    양자 회로를 빠르게 실행하고 결과만 반환합니다 (시각화 없음).
    
    Parameters
    ----------
    qc : QuantumCircuit
        실행할 양자 회로
    shots : int, default=1000
        측정 샷 수
    backend : Backend, optional
        사용할 백엔드 (None이면 AerSimulator)
    show_results : bool, default=False
        측정 결과를 텍스트로 출력할지 여부
    compare_with_ideal : bool, default=False
        하드웨어 실행 시 시뮬레이터 결과도 함께 반환
    
    Returns
    -------
    dict or tuple of dict
        측정 결과 counts (compare_with_ideal=True이고 하드웨어면 (ideal_counts, hw_counts))
    """
    circuit = qc.copy()
    if not circuit.cregs:
        circuit.measure_all()
    
    if backend is None:
        backend = AerSimulator()
    
    from qiskit import transpile
    is_hardware = hasattr(backend, 'simulator') and not backend.simulator
    
    if is_hardware:
        circuit = transpile(circuit, backend=backend, optimization_level=3)
        
        if compare_with_ideal:
            # 원본 회로에서 이론적 확률 계산
            original_circuit = qc.copy()
            if not original_circuit.cregs:
                original_circuit.measure_all()
            ideal_counts = _get_ideal_counts(original_circuit, shots)
            hw_counts = _run_circuit(circuit, backend, shots)
            
            if show_results:
                print(f"\n[ Quick Run Results ] shots={shots}")
                print("\n<Ideal (Simulator)>")
                for state, count in sorted(ideal_counts.items(), key=lambda x: x[1], reverse=True):
                    probability = count / shots * 100
                    print(f"|{state}⟩: {count:4d}회 ({probability:6.2f}%)")
                
                print(f"\n<Hardware ({backend.name})>")
                for state, count in sorted(hw_counts.items(), key=lambda x: x[1], reverse=True):
                    probability = count / shots * 100
                    print(f"|{state}⟩: {count:4d}회 ({probability:6.2f}%)")
            
            return ideal_counts, hw_counts
    
    counts = _run_circuit(circuit, backend, shots)
    
    if show_results:
        backend_name = getattr(backend, 'name', 'Simulator')
        print(f"\n[ Quick Run Results ] shots={shots} ({backend_name})")
        for state, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            probability = count / shots * 100
            print(f"|{state}⟩: {count:4d}회 ({probability:6.2f}%)")
    
    return counts


def circuit_info(qc: QuantumCircuit):
    """
    양자 회로의 상세 정보를 출력합니다.
    
    Parameters
    ----------
    qc : QuantumCircuit
        분석할 양자 회로
    """
    print("\n[ Circuit Information ]")
    print(f"Qubits: {qc.num_qubits}, Classical bits: {qc.num_clbits}")
    print(f"Gates: {qc.size()}, Depth: {qc.depth()}")
    print(f"\nGate counts:")
    for gate, count in qc.count_ops().items():
        print(f"  {gate}: {count}")


# 사용 예제
if __name__ == "__main__":
    print("Qiskit 유틸리티가 로드되었습니다!")
    print("\n사용 가능한 함수:")
    print("  - run_and_visualize(qc, shots=1000, backend=None, show_circuit=True, show_histogram=True, show_results=True)")
    print("  - compare_circuits(circuits, labels=None, shots=1000, backend=None, show_circuit=True, show_histogram=True, show_results=True)")
    print("  - quick_run(qc, shots=1000, backend=None, show_results=False)")
    print("  - circuit_info(qc)")
    print("\n예제:")
    print("  qc = QuantumCircuit(2)")
    print("  qc.h(0)")
    print("  qc.cx(0, 1)")
    print("  counts = run_and_visualize(qc)")
    print("\n  # 결과 출력 없이 히스토그램만")
    print("  counts = run_and_visualize(qc, show_results=False)")
    print("\n  # 하드웨어 사용 시 자동으로 시뮬레이터 결과와 비교")
    print("  ideal, hw = run_and_visualize(qc, backend=hardware)")
